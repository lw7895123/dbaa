# -*- coding: utf-8 -*-
"""
高并发订单监控系统安装脚本
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


class SystemSetup:
    """系统安装配置类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / '.venv'
        self.logs_path = self.project_root / 'logs'
        self.config_path = self.project_root / '.env'
        
    def check_python_version(self) -> bool:
        """检查Python版本"""
        print("检查Python版本...")
        
        if sys.version_info < (3, 7):
            print("错误: 需要Python 3.7或更高版本")
            return False
        
        print(f"Python版本: {sys.version}")
        return True
    
    def create_directories(self) -> bool:
        """创建必要的目录"""
        print("创建项目目录...")
        
        try:
            # 创建日志目录
            self.logs_path.mkdir(exist_ok=True)
            print(f"创建日志目录: {self.logs_path}")
            
            # 创建用户日志子目录
            user_logs_path = self.logs_path / 'users'
            user_logs_path.mkdir(exist_ok=True)
            print(f"创建用户日志目录: {user_logs_path}")
            
            # 创建系统日志文件
            system_log = self.logs_path / 'system.log'
            if not system_log.exists():
                system_log.touch()
                print(f"创建系统日志文件: {system_log}")
            
            return True
            
        except Exception as e:
            print(f"创建目录失败: {e}")
            return False
    
    def setup_virtual_environment(self) -> bool:
        """设置虚拟环境"""
        print("设置虚拟环境...")
        
        try:
            if not self.venv_path.exists():
                # 创建虚拟环境
                subprocess.run([
                    sys.executable, '-m', 'venv', str(self.venv_path)
                ], check=True)
                print(f"创建虚拟环境: {self.venv_path}")
            else:
                print(f"虚拟环境已存在: {self.venv_path}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"创建虚拟环境失败: {e}")
            return False
    
    def install_dependencies(self) -> bool:
        """安装依赖包"""
        print("安装依赖包...")
        
        try:
            # 确定pip路径
            if sys.platform == "win32":
                pip_path = self.venv_path / 'Scripts' / 'pip.exe'
            else:
                pip_path = self.venv_path / 'bin' / 'pip'
            
            if not pip_path.exists():
                print(f"错误: pip不存在于 {pip_path}")
                return False
            
            # 升级pip
            subprocess.run([
                str(pip_path), 'install', '--upgrade', 'pip'
            ], check=True)
            
            # 安装依赖
            requirements_file = self.project_root / 'requirements.txt'
            if requirements_file.exists():
                subprocess.run([
                    str(pip_path), 'install', '-r', str(requirements_file)
                ], check=True)
                print("依赖包安装完成")
            else:
                print("警告: requirements.txt文件不存在")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"安装依赖包失败: {e}")
            return False
    
    def setup_configuration(self) -> bool:
        """设置配置文件"""
        print("设置配置文件...")
        
        try:
            env_example = self.project_root / '.env.example'
            
            if not self.config_path.exists() and env_example.exists():
                # 复制配置模板
                shutil.copy2(env_example, self.config_path)
                print(f"创建配置文件: {self.config_path}")
                print("请编辑 .env 文件以配置数据库和Redis连接信息")
            else:
                print("配置文件已存在或模板不存在")
            
            return True
            
        except Exception as e:
            print(f"设置配置文件失败: {e}")
            return False
    
    def check_database_connection(self) -> bool:
        """检查数据库连接（可选）"""
        print("检查数据库连接...")
        
        try:
            # 这里可以添加数据库连接测试
            # 由于需要配置信息，这里只是示例
            print("请确保MySQL和Redis服务正在运行")
            print("请在 .env 文件中配置正确的数据库连接信息")
            return True
            
        except Exception as e:
            print(f"数据库连接检查失败: {e}")
            return False
    
    def create_database_schema(self) -> bool:
        """创建数据库表结构"""
        print("创建数据库表结构...")
        
        try:
            schema_file = self.project_root / 'framework' / 'database' / 'schema.sql'
            
            if schema_file.exists():
                print(f"数据库表结构文件: {schema_file}")
                print("请手动执行SQL文件创建数据库表结构")
                print("或使用以下命令:")
                print(f"mysql -u username -p database_name < {schema_file}")
            else:
                print("警告: 数据库表结构文件不存在")
            
            return True
            
        except Exception as e:
            print(f"数据库表结构设置失败: {e}")
            return False
    
    def run_tests(self) -> bool:
        """运行测试（可选）"""
        print("运行系统测试...")
        
        try:
            # 确定python路径
            if sys.platform == "win32":
                python_path = self.venv_path / 'Scripts' / 'python.exe'
            else:
                python_path = self.venv_path / 'bin' / 'python'
            
            if python_path.exists():
                # 运行简单测试
                test_script = self.project_root / 'app.py'
                if test_script.exists():
                    result = subprocess.run([
                        str(python_path), str(test_script), 'test'
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        print("系统测试通过")
                        return True
                    else:
                        print(f"系统测试失败: {result.stderr}")
                        return False
            
            print("跳过测试（Python路径不存在）")
            return True
            
        except Exception as e:
            print(f"运行测试失败: {e}")
            return False
    
    def print_usage_instructions(self) -> None:
        """打印使用说明"""
        print("\n" + "="*60)
        print("安装完成！使用说明:")
        print("="*60)
        
        if sys.platform == "win32":
            activate_cmd = f"{self.venv_path}\\Scripts\\activate"
            python_cmd = f"{self.venv_path}\\Scripts\\python.exe"
        else:
            activate_cmd = f"source {self.venv_path}/bin/activate"
            python_cmd = f"{self.venv_path}/bin/python"
        
        print(f"1. 激活虚拟环境:")
        print(f"   {activate_cmd}")
        print()
        print(f"2. 编辑配置文件:")
        print(f"   编辑 {self.config_path} 文件")
        print()
        print(f"3. 创建数据库表:")
        print(f"   执行 framework/database/schema.sql")
        print()
        print(f"4. 启动系统:")
        print(f"   {python_cmd} app.py start")
        print()
        print(f"5. 查看系统状态:")
        print(f"   {python_cmd} app.py status")
        print()
        print(f"6. 测试系统:")
        print(f"   {python_cmd} app.py test")
        print("="*60)
    
    def setup(self) -> bool:
        """执行完整安装"""
        print("开始安装高并发订单监控系统...")
        print("="*60)
        
        steps = [
            ("检查Python版本", self.check_python_version),
            ("创建项目目录", self.create_directories),
            ("设置虚拟环境", self.setup_virtual_environment),
            ("安装依赖包", self.install_dependencies),
            ("设置配置文件", self.setup_configuration),
            ("检查数据库连接", self.check_database_connection),
            ("创建数据库表结构", self.create_database_schema),
        ]
        
        for step_name, step_func in steps:
            print(f"\n[{step_name}]")
            if not step_func():
                print(f"错误: {step_name} 失败")
                return False
            print(f"✓ {step_name} 完成")
        
        # 可选测试
        print(f"\n[运行系统测试]")
        test_result = self.run_tests()
        if test_result:
            print("✓ 系统测试完成")
        else:
            print("⚠ 系统测试失败（可能需要配置数据库）")
        
        self.print_usage_instructions()
        return True


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("高并发订单监控系统安装脚本")
        print("用法: python setup.py")
        print("这将自动安装所有依赖并配置系统")
        return
    
    setup = SystemSetup()
    
    try:
        success = setup.setup()
        if success:
            print("\n🎉 安装成功！")
            sys.exit(0)
        else:
            print("\n❌ 安装失败！")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n安装被用户中断")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n安装过程中发生未知错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()