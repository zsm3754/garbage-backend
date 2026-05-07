# 【仅填你的MySQL信息】
DB_CONFIG = {
    "host": "rm-cn-szl4rue4m0001v.rwlb.rds.aliyuncs.com",  # 改：RDS 内网地址
    "port": 3306,
    "user": "garbage_app",           # 改：RDS 账号（不是 root）
    "password": "Zsm044688",         # 改：RDS 密码
    "database": "garbage_classification_db",  # 检查这个数据库是否在RDS中存在
    "charset": "utf8mb4"
}

# 服务配置
SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000
}