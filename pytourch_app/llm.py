# 大语言模型训练完整案例
# 以训练一个中等规模的GPT模型为例

import os
import math
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torch.nn.parallel import DistributedDataParallel as DDP
import torch.distributed as dist
import torch.multiprocessing as mp
from transformers import GPT2Tokenizer, GPT2Config
import numpy as np
import json
from tqdm import tqdm
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPTModel(nn.Module):
    """简化版GPT模型实现"""

    def __init__(self, config):
        super().__init__()
        self.config = config

        # Token嵌入和位置嵌入
        self.token_embedding = nn.Embedding(config.vocab_size, config.hidden_size)
        self.position_embedding = nn.Embedding(config.max_position_embeddings, config.hidden_size)

        # Transformer块
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.num_hidden_layers)
        ])

        # 最终层归一化
        self.ln_f = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_epsilon)

        # 输出头
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)

        # 参数初始化
        self.apply(self._init_weights)

    def _init_weights(self, module):
        """参数初始化"""
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
        elif isinstance(module, nn.LayerNorm):
            torch.nn.init.zeros_(module.bias)
            torch.nn.init.ones_(module.weight)

    def forward(self, input_ids, attention_mask=None, labels=None):
        batch_size, seq_len = input_ids.shape

        # 创建位置ID
        position_ids = torch.arange(0, seq_len, dtype=torch.long, device=input_ids.device)
        position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)

        # 嵌入
        token_embeddings = self.token_embedding(input_ids)
        position_embeddings = self.position_embedding(position_ids)
        hidden_states = token_embeddings + position_embeddings

        # 通过Transformer块
        for block in self.transformer_blocks:
            hidden_states = block(hidden_states, attention_mask)

        # 最终层归一化
        hidden_states = self.ln_f(hidden_states)

        # 计算logits
        lm_logits = self.lm_head(hidden_states)

        loss = None
        if labels is not None:
            # 计算语言建模损失
            shift_logits = lm_logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))

        return {"loss": loss, "logits": lm_logits}


class TransformerBlock(nn.Module):
    """Transformer块"""

    def __init__(self, config):
        super().__init__()
        self.ln_1 = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_epsilon)
        self.attn = MultiHeadAttention(config)
        self.ln_2 = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_epsilon)
        self.mlp = MLP(config)

    def forward(self, hidden_states, attention_mask=None):
        # 自注意力
        residual = hidden_states
        hidden_states = self.ln_1(hidden_states)
        attn_output = self.attn(hidden_states, attention_mask)
        hidden_states = residual + attn_output

        # 前馈网络
        residual = hidden_states
        hidden_states = self.ln_2(hidden_states)
        mlp_output = self.mlp(hidden_states)
        hidden_states = residual + mlp_output

        return hidden_states


class MultiHeadAttention(nn.Module):
    """多头注意力机制"""

    def __init__(self, config):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.head_dim = self.hidden_size // self.num_heads

        assert self.head_dim * self.num_heads == self.hidden_size

        self.q_proj = nn.Linear(self.hidden_size, self.hidden_size)
        self.k_proj = nn.Linear(self.hidden_size, self.hidden_size)
        self.v_proj = nn.Linear(self.hidden_size, self.hidden_size)
        self.out_proj = nn.Linear(self.hidden_size, self.hidden_size)

        self.dropout = nn.Dropout(config.attention_probs_dropout_prob)

    def forward(self, hidden_states, attention_mask=None):
        batch_size, seq_len, hidden_size = hidden_states.shape

        # 计算Q, K, V
        query = self.q_proj(hidden_states)
        key = self.k_proj(hidden_states)
        value = self.v_proj(hidden_states)

        # 重塑为多头形式
        query = query.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        key = key.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        value = value.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        # 计算注意力分数
        attention_scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(self.head_dim)

        # 应用因果掩码（确保只能看到之前的token）
        causal_mask = torch.tril(torch.ones(seq_len, seq_len, device=hidden_states.device))
        attention_scores = attention_scores.masked_fill(causal_mask == 0, float('-inf'))

        # 应用注意力掩码
        if attention_mask is not None:
            attention_scores = attention_scores + attention_mask

        # Softmax
        attention_probs = torch.softmax(attention_scores, dim=-1)
        attention_probs = self.dropout(attention_probs)

        # 应用注意力权重
        context = torch.matmul(attention_probs, value)

        # 重塑输出
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, hidden_size)
        output = self.out_proj(context)

        return output


class MLP(nn.Module):
    """前馈网络"""

    def __init__(self, config):
        super().__init__()
        self.c_fc = nn.Linear(config.hidden_size, 4 * config.hidden_size)
        self.gelu = nn.GELU()
        self.c_proj = nn.Linear(4 * config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.resid_pdrop)

    def forward(self, hidden_states):
        hidden_states = self.c_fc(hidden_states)
        hidden_states = self.gelu(hidden_states)
        hidden_states = self.c_proj(hidden_states)
        hidden_states = self.dropout(hidden_states)
        return hidden_states


class TextDataset(Dataset):
    """文本数据集"""

    def __init__(self, texts, tokenizer, max_length=512):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]

        # 分词
        encoded = self.tokenizer.encode(
            text,
            max_length=self.max_length,
            truncation=True,
            padding='max_length',
            return_tensors='pt'
        )

        input_ids = encoded.squeeze()

        return {
            'input_ids': input_ids,
            'labels': input_ids.clone()  # 对于语言建模，labels就是input_ids
        }


def load_data(data_path):
    """加载训练数据"""
    logger.info(f"从 {data_path} 加载数据...")

    texts = []
    if data_path.endswith('.json'):
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            texts = [item['text'] for item in data]
    elif data_path.endswith('.txt'):
        with open(data_path, 'r', encoding='utf-8') as f:
            texts = f.read().split('\n\n')  # 按段落分割

    logger.info(f"加载了 {len(texts)} 个文本样本")
    return texts


class TrainingConfig:
    """训练配置"""

    def __init__(self):
        # 模型配置
        self.vocab_size = 50257  # GPT-2词汇表大小
        self.hidden_size = 768
        self.num_hidden_layers = 12
        self.num_attention_heads = 12
        self.max_position_embeddings = 1024
        self.layer_norm_epsilon = 1e-5
        self.attention_probs_dropout_prob = 0.1
        self.resid_pdrop = 0.1

        # 训练配置
        self.batch_size = 8
        self.learning_rate = 5e-5
        self.num_epochs = 3
        self.warmup_steps = 1000
        self.max_grad_norm = 1.0
        self.save_steps = 1000
        self.eval_steps = 500
        self.logging_steps = 100

        # 路径配置
        self.data_path = "data/train.txt"
        self.output_dir = "outputs"
        self.log_dir = "logs"


def setup_distributed(rank, world_size):
    """设置分布式训练"""
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'
    dist.init_process_group("nccl", rank=rank, world_size=world_size)
    torch.cuda.set_device(rank)


def cleanup_distributed():
    """清理分布式训练"""
    dist.destroy_process_group()


def train_epoch(model, dataloader, optimizer, scheduler, device, rank):
    """训练一个epoch"""
    model.train()
    total_loss = 0
    num_batches = len(dataloader)

    progress_bar = tqdm(dataloader, desc="Training", disable=rank != 0)

    for step, batch in enumerate(progress_bar):
        # 将数据移到GPU
        input_ids = batch['input_ids'].to(device)
        labels = batch['labels'].to(device)

        # 前向传播
        outputs = model(input_ids=input_ids, labels=labels)
        loss = outputs['loss']

        # 反向传播
        optimizer.zero_grad()
        loss.backward()

        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        # 更新参数
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

        # 更新进度条
        if rank == 0:
            progress_bar.set_postfix({
                'loss': f'{loss.item():.4f}',
                'avg_loss': f'{total_loss / (step + 1):.4f}',
                'lr': f'{scheduler.get_last_lr()[0]:.2e}'
            })

    return total_loss / num_batches


def evaluate(model, dataloader, device, rank):
    """评估模型"""
    model.eval()
    total_loss = 0
    num_batches = len(dataloader)

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating", disable=rank != 0):
            input_ids = batch['input_ids'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids=input_ids, labels=labels)
            loss = outputs['loss']
            total_loss += loss.item()

    return total_loss / num_batches


def save_checkpoint(model, optimizer, scheduler, epoch, step, loss, output_dir):
    """保存检查点"""
    checkpoint = {
        'epoch': epoch,
        'step': step,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict(),
        'loss': loss,
    }

    checkpoint_path = os.path.join(output_dir, f'checkpoint-epoch-{epoch}-step-{step}.pt')
    torch.save(checkpoint, checkpoint_path)
    logger.info(f"检查点已保存到 {checkpoint_path}")


def main_worker(rank, world_size, config):
    """主训练函数"""
    # 设置分布式训练
    setup_distributed(rank, world_size)
    device = torch.device(f'cuda:{rank}')

    # 创建输出目录
    os.makedirs(config.output_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)

    # 初始化tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokenizer.pad_token = tokenizer.eos_token

    # 加载数据
    texts = load_data(config.data_path)

    # 创建数据集
    train_size = int(0.9 * len(texts))
    train_texts = texts[:train_size]
    val_texts = texts[train_size:]

    train_dataset = TextDataset(train_texts, tokenizer, max_length=config.max_position_embeddings)
    val_dataset = TextDataset(val_texts, tokenizer, max_length=config.max_position_embeddings)

    # 创建数据加载器
    train_sampler = torch.utils.data.distributed.DistributedSampler(
        train_dataset, num_replicas=world_size, rank=rank
    )
    train_dataloader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        sampler=train_sampler,
        num_workers=4,
        pin_memory=True
    )

    val_sampler = torch.utils.data.distributed.DistributedSampler(
        val_dataset, num_replicas=world_size, rank=rank
    )
    val_dataloader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        sampler=val_sampler,
        num_workers=4,
        pin_memory=True
    )

    # 创建模型配置
    model_config = GPT2Config(
        vocab_size=config.vocab_size,
        n_embd=config.hidden_size,
        n_layer=config.num_hidden_layers,
        n_head=config.num_attention_heads,
        n_positions=config.max_position_embeddings,
        layer_norm_epsilon=config.layer_norm_epsilon,
        attn_pdrop=config.attention_probs_dropout_prob,
        resid_pdrop=config.resid_pdrop,
    )

    # 创建模型
    model = GPTModel(model_config).to(device)

    # 包装为分布式模型
    model = DDP(model, device_ids=[rank])

    # 创建优化器和调度器
    optimizer = optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=0.01)

    total_steps = len(train_dataloader) * config.num_epochs
    scheduler = optim.lr_scheduler.LinearLR(
        optimizer,
        start_factor=0.1,
        end_factor=1.0,
        total_iters=config.warmup_steps
    )

    # 训练循环
    best_val_loss = float('inf')
    global_step = 0

    for epoch in range(config.num_epochs):
        if rank == 0:
            logger.info(f"开始第 {epoch + 1}/{config.num_epochs} 轮训练")

        train_sampler.set_epoch(epoch)

        # 训练
        train_loss = train_epoch(model, train_dataloader, optimizer, scheduler, device, rank)

        # 评估
        val_loss = evaluate(model, val_dataloader, device, rank)

        if rank == 0:
            logger.info(f"Epoch {epoch + 1}: Train Loss = {train_loss:.4f}, Val Loss = {val_loss:.4f}")

            # 保存最佳模型
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                save_checkpoint(
                    model.module, optimizer, scheduler,
                    epoch, global_step, val_loss, config.output_dir
                )

        global_step += len(train_dataloader)

    # 清理
    cleanup_distributed()


def generate_text(model, tokenizer, prompt, max_length=100, device='cuda'):
    """生成文本"""
    model.eval()

    # 编码输入
    input_ids = tokenizer.encode(prompt, return_tensors='pt').to(device)

    with torch.no_grad():
        for _ in range(max_length):
            outputs = model(input_ids)
            logits = outputs['logits']

            # 获取下一个token
            next_token_logits = logits[0, -1, :]
            next_token = torch.multinomial(torch.softmax(next_token_logits, dim=-1), 1)

            # 添加到序列
            input_ids = torch.cat([input_ids, next_token.unsqueeze(0)], dim=-1)

            # 如果生成了结束符就停止
            if next_token.item() == tokenizer.eos_token_id:
                break

    # 解码生成的文本
    generated_text = tokenizer.decode(input_ids[0], skip_special_tokens=True)
    return generated_text


if __name__ == "__main__":
    # 创建配置
    config = TrainingConfig()

    # 检查GPU数量
    world_size = torch.cuda.device_count()

    if world_size > 1:
        # 多GPU分布式训练
        mp.spawn(main_worker, args=(world_size, config), nprocs=world_size, join=True)
    else:
        # 单GPU训练
        main_worker(0, 1, config)

    # 训练完成后测试生成
    logger.info("训练完成，测试文本生成...")

    # 加载最佳模型进行测试
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokenizer.pad_token = tokenizer.eos_token

    # 这里需要根据实际保存的检查点路径加载模型
    # checkpoint = torch.load('outputs/best_model.pt')
    # model.load_state_dict(checkpoint['model_state_dict'])

    # generated = generate_text(model, tokenizer, "今天天气", max_length=50, device=device)
    # print(f"生成的文本: {generated}")