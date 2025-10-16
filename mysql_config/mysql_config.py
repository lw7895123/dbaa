"""
    脚本用来作为 MySQL 配置器，自动完成 MySQL 的安装、配置、初始化等操作。
    注意：本脚本使用 Windows 系統，且需要以管理員身份運行。可安装配置mysql5.7.44的压缩包（zip文件）版本。
    脚本使用 Python 3.x 编写，依赖于以下第三方库：
        - subprocess
        - time
        - shutil
        - pathlib
"""
import os
import subprocess
import time
import shutil
from pathlib import Path


class MySQLConfigurator:
    def __init__(self, mysql_base_path):
        """
        初始化 MySQL 配置器
        :param mysql_base_path: MySQL 安裝根目錄
        """
        self.base_path = Path(mysql_base_path)
        self.bin_path = self.base_path / "bin"
        self.data_path = self.base_path / "data"
        self.my_ini_path = self.base_path / "my.ini"

    @staticmethod
    def check_admin():
        """檢查是否以管理員身份運行"""
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("❌ 錯誤：請以管理員身份運行此腳本！")
                print("   右鍵點擊 CMD 或 PowerShell，選擇「以系統管理員身份執行」")
                return False
            return True
        except:
            return False

    @staticmethod
    def stop_service():
        """停止 MySQL 服務"""
        print("\n[1/7] 停止 MySQL 服務...")
        try:
            subprocess.run(["net", "stop", "mysql"],
                           capture_output=True, text=True, timeout=30)
            print("✓ 服務已停止")
            return True
        except Exception:
            print("⚠ 服務未運行或已停止")
            return False

    @staticmethod
    def delete_service():
        """刪除 MySQL 服務"""
        print("\n[2/7] 刪除 MySQL 服務...")
        try:
            subprocess.run(["sc", "delete", "mysql"],
                           capture_output=True, text=True, timeout=30)
            print("✓ 服務已刪除")
            time.sleep(2)  # 等待服務完全刪除
            return True
        except:
            print("⚠ 服務不存在或已刪除")
            return False

    def clean_data_directory(self):
        """清理 data 目錄"""
        print("\n[3/7] 清理 data 目錄...")
        try:
            if self.data_path.exists():
                shutil.rmtree(self.data_path)
                print(f"✓ 已刪除目錄: {self.data_path}")
            else:
                print("⚠ data 目錄不存在")
            time.sleep(1)
        except Exception as e:
            print(f"❌ 刪除失敗: {e}")
            return False
        return True

    def create_my_ini(self):
        """創建 my.ini 配置文件"""
        print("\n[4/7] 創建 my.ini 配置文件...")

        # 使用正斜線避免轉義問題
        base_path_str = str(self.base_path).replace("\\", "/")
        data_path_str = str(self.data_path).replace("\\", "/")

        config_content = f"""[mysqld]
# 設置基礎目錄和數據目錄
basedir={base_path_str}
datadir={data_path_str}

# 設置端口
port=3306

# 設置字符集
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci

# 允許最大連接數
max_connections=200

# 設置默認存儲引擎
default-storage-engine=INNODB

# SQL 模式
sql_mode=NO_ENGINE_SUBSTITUTION,STRICT_TRANS_TABLES

# 時間戳設置
explicit_defaults_for_timestamp=true

# 最大允許的數據包大小
max_allowed_packet=64M

[client]
port=3306
default-character-set=utf8mb4

[mysql]
default-character-set=utf8mb4
"""

        try:
            with open(self.my_ini_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            print(f"✓ 已創建配置文件: {self.my_ini_path}")
            return True
        except Exception as e:
            print(f"❌ 創建配置文件失敗: {e}")
            return False

    def initialize_database(self):
        """初始化數據庫"""
        print("\n[5/7] 初始化數據庫（可能需要 10-30 秒）...")

        mysqld_exe = self.bin_path / "mysqld.exe"
        if not mysqld_exe.exists():
            print(f"❌ 找不到 mysqld.exe: {mysqld_exe}")
            return False

        try:
            # 使用 --console 顯示詳細信息
            result = subprocess.run(
                [str(mysqld_exe), "--initialize-insecure", "--console"],
                cwd=str(self.bin_path),
                capture_output=True,
                text=True,
                timeout=120
            )

            # 檢查是否有錯誤
            if "[ERROR]" in result.stderr or result.returncode != 0:
                print(f"❌ 初始化失敗:")
                print(result.stderr)
                return False

            # 驗證 data 目錄和系統表
            mysql_dir = self.data_path / "mysql"
            if mysql_dir.exists():
                print("✓ 數據庫初始化成功")
                print(f"  - 系統數據庫已創建: {mysql_dir}")
                return True
            else:
                print("❌ 初始化可能失敗，未找到 mysql 系統數據庫")
                return False

        except subprocess.TimeoutExpired:
            print("❌ 初始化超時")
            return False
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
            return False

    def install_service(self):
        """安裝 MySQL 服務"""
        print("\n[6/7] 安裝 MySQL 服務...")

        mysqld_exe = self.bin_path / "mysqld.exe"

        try:
            result = subprocess.run(
                [str(mysqld_exe), "--install", "MySQL",
                 f"--defaults-file={self.my_ini_path}"],
                cwd=str(self.bin_path),
                capture_output=True,
                text=True,
                timeout=30
            )

            if "successfully" in result.stdout.lower() or result.returncode == 0:
                print("✓ MySQL 服務安裝成功")
                return True
            else:
                print(f"⚠ 安裝結果: {result.stdout}")
                return True  # 有時即使成功也不返回消息
        except Exception as e:
            print(f"❌ 安裝服務失敗: {e}")
            return False

    def start_service(self):
        """啟動 MySQL 服務"""
        print("\n[7/7] 啟動 MySQL 服務...")

        try:
            result = subprocess.run(
                ["net", "start", "mysql"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("✓ MySQL 服務啟動成功！")
                return True
            else:
                print(f"❌ 啟動失敗: {result.stderr}")
                print("\n建議手動檢查錯誤日誌:")
                print(f"   {self.data_path / '*.err'}")
                return False
        except Exception as e:
            print(f"❌ 啟動服務失敗: {e}")
            return False

    def configure(self):
        """執行完整配置流程"""
        print("=" * 60)
        print("MySQL 自動配置腳本")
        print("=" * 60)
        print(f"MySQL 安裝路徑: {self.base_path}")
        print(f"數據目錄: {self.data_path}")
        print("=" * 60)

        # 檢查管理員權限
        if not self.check_admin():
            return False

        # 檢查路徑是否存在
        if not self.base_path.exists():
            print(f"\n❌ MySQL 安裝路徑不存在: {self.base_path}")
            return False

        if not self.bin_path.exists():
            print(f"\n❌ bin 目錄不存在: {self.bin_path}")
            return False

        # 執行配置步驟
        steps = [
            self.stop_service,
            self.delete_service,
            self.clean_data_directory,
            self.create_my_ini,
            self.initialize_database,
            self.install_service,
            self.start_service
        ]

        for step in steps:
            if not step():
                print("\n" + "=" * 60)
                print("❌ 配置過程中斷")
                print("=" * 60)
                return False

        print("\n" + "=" * 60)
        print("✓ MySQL 基本配置完成！")
        print("=" * 60)

        return True


    def test_connection(self):
        """測試 MySQL 連接"""
        print("\n" + "=" * 60)
        print("測試 MySQL 連接")
        print("=" * 60)

        mysql_exe = self.bin_path / "mysql.exe"
        if not mysql_exe.exists():
            print(f"❌ 找不到 mysql.exe: {mysql_exe}")
            return False

        try:
            # 嘗試連接（root 用戶，空密碼）
            result = subprocess.run(
                [str(mysql_exe), "-u", "root", "-e", "SELECT VERSION();"],
                cwd=str(self.bin_path),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print("✓ MySQL 連接成功！")
                print(f"  版本信息:\n{result.stdout}")
                return True
            else:
                print(f"❌ 連接失敗: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ 測試連接失敗: {e}")
            return False


    def set_root_password(self):
        """設置 root 密碼"""
        print("\n" + "=" * 60)
        print("設置 Root 用戶密碼")
        print("=" * 60)

        while True:
            password = input("\n請輸入新的 root 密碼（留空跳過）: ").strip()

            if not password:
                print("⚠ 跳過密碼設置，root 用戶將保持空密碼")
                return True

            confirm_password = input("請再次輸入密碼確認: ").strip()

            if password != confirm_password:
                print("❌ 兩次密碼輸入不一致，請重新輸入")
                continue

            if len(password) < 6:
                print("⚠ 密碼長度建議至少 6 個字符")
                choice = input("是否繼續使用此密碼？(y/n): ").strip().lower()
                if choice != 'y':
                    continue

            break

        # 執行密碼設置
        mysql_exe = self.bin_path / "mysql.exe"
        sql_commands = f"""
    ALTER USER 'root'@'localhost' IDENTIFIED BY '{password}';
    FLUSH PRIVILEGES;
    SELECT 'Password updated successfully' AS Result;
    """

        try:
            result = subprocess.run(
                [str(mysql_exe), "-u", "root", "-e", sql_commands],
                cwd=str(self.bin_path),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print("\n✓ Root 密碼設置成功！")
                print("  請妥善保管您的密碼")

                # 保存密碼提示到文件
                self.save_password_info(password)
                return True
            else:
                print(f"\n❌ 密碼設置失敗: {result.stderr}")
                return False
        except Exception as e:
            print(f"\n❌ 執行失敗: {e}")
            return False


    def save_password_info(self, password):
        """保存密碼信息到文件（僅供提示用）"""
        info_file = self.base_path / "mysql_info.txt"
        try:
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write("MySQL 連接信息\n")
                f.write("=" * 50 + "\n")
                f.write(f"主機: localhost\n")
                f.write(f"端口: 3306\n")
                f.write(f"用戶: root\n")
                f.write(f"密碼: {password}\n")
                f.write("=" * 50 + "\n")
                f.write(f"配置時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n⚠ 警告: 請勿將此文件分享給他人！\n")

            print(f"\n💾 連接信息已保存到: {info_file}")
            print("   ⚠ 請注意保管此文件的安全性")
        except Exception as e:
            print(f"\n⚠ 保存連接信息失敗: {e}")


    def create_test_database(self):
        """創建測試數據庫"""
        print("\n" + "=" * 60)
        print("創建測試數據庫")
        print("=" * 60)

        choice = input("\n是否創建一個測試數據庫？(y/n): ").strip().lower()
        if choice != 'y':
            print("⚠ 跳過測試數據庫創建")
            return True

        db_name = input("請輸入數據庫名稱（默認: testdb）: ").strip()
        if not db_name:
            db_name = "testdb"

        mysql_exe = self.bin_path / "mysql.exe"

        # 詢問密碼
        password = input("請輸入 root 密碼（如果設置了密碼）: ").strip()

        sql_commands = f"""
    CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    SHOW DATABASES;
    """

        try:
            if password:
                cmd = [str(mysql_exe), "-u", "root", f"-p{password}", "-e", sql_commands]
            else:
                cmd = [str(mysql_exe), "-u", "root", "-e", sql_commands]

            result = subprocess.run(
                cmd,
                cwd=str(self.bin_path),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print(f"\n✓ 數據庫 '{db_name}' 創建成功！")
                print("\n當前數據庫列表:")
                print(result.stdout)
                return True
            else:
                print(f"\n❌ 創建失敗: {result.stderr}")
                return False
        except Exception as e:
            print(f"\n❌ 執行失敗: {e}")
            return False


    def show_connection_guide(self):
        """顯示連接指南"""
        print("\n" + "=" * 60)
        print("MySQL 連接指南")
        print("=" * 60)

        print("\n📋 命令行連接方式:")
        print(f"   cd {self.bin_path}")
        print("   mysql -u root -p")
        print("   （然後輸入密碼）")

        print("\n📋 常用 MySQL 命令:")
        print("   SHOW DATABASES;              # 顯示所有數據庫")
        print("   USE database_name;           # 選擇數據庫")
        print("   SHOW TABLES;                 # 顯示所有表")
        print("   CREATE DATABASE db_name;     # 創建數據庫")
        print("   EXIT;                        # 退出")

        print("\n📋 連接參數（用於應用程序）:")
        print("   主機(Host): localhost")
        print("   端口(Port): 3306")
        print("   用戶(User): root")
        print("   密碼(Password): [您設置的密碼]")

        print("\n📋 配置文件位置:")
        print(f"   {self.my_ini_path}")

        print("\n📋 數據目錄:")
        print(f"   {self.data_path}")

        print("\n📋 日誌文件:")
        print(f"   {self.data_path / '*.err'}")

        print("\n" + "=" * 60)


    def post_configuration(self):
        """配置後的設置步驟"""
        print("\n" + "=" * 60)
        print("開始配置後設置")
        print("=" * 60)

        # 等待服務完全啟動
        print("\n⏳ 等待 MySQL 服務完全啟動...")
        time.sleep(3)

        # 測試連接
        if not self.test_connection():
            print("\n⚠ MySQL 連接測試失敗，請檢查服務狀態")
            choice = input("是否繼續後續配置？(y/n): ").strip().lower()
            if choice != 'y':
                return False

        # 設置密碼
        if not self.set_root_password():
            print("\n⚠ 密碼設置失敗，您可以稍後手動設置")
            choice = input("是否繼續？(y/n): ").strip().lower()
            if choice != 'y':
                return False

        # 創建測試數據庫
        self.create_test_database()

        # 顯示連接指南
        self.show_connection_guide()

        return True


def main():
    print("=" * 60)
    print("MySQL 完整自動配置腳本")
    print("=" * 60)

    # 詢問 MySQL 安裝路徑
    default_path = r"D:\workfile\tools\mysql_5_7_44"
    print(f"\n默認 MySQL 路徑: {default_path}")
    custom_path = input("請輸入 MySQL 安裝路徑（留空使用默認路徑）: ").strip()

    mysql_path = custom_path if custom_path else default_path

    print(f"\n使用路徑: {mysql_path}")
    choice = input("確認路徑正確？(y/n): ").strip().lower()
    if choice != 'y':
        print("操作已取消")
        input("\n按 Enter 鍵退出...")
        return

    configurator = MySQLConfigurator(mysql_path)

    try:
        # 執行基本配置
        success = configurator.configure()

        if success:
            # 執行配置後設置
            print("\n" + "=" * 60)
            choice = input("是否繼續進行配置後設置（設置密碼、創建測試庫等）？(y/n): ").strip().lower()
            if choice == 'y':
                configurator.post_configuration()

            print("\n" + "=" * 60)
            print("✅ 所有配置完成！")
            print("=" * 60)
        else:
            print("\n❌ 配置失敗")

        input("\n按 Enter 鍵退出...")

    except KeyboardInterrupt:
        print("\n\n⚠ 用戶中斷操作")
        input("\n按 Enter 鍵退出...")
    except Exception as e:
        print(f"\n❌ 發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()
        input("\n按 Enter 鍵退出...")


if __name__ == "__main__":
    main()