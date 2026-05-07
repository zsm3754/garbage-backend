from sqlalchemy import create_engine, Column, Integer, String, Text, DECIMAL, CHAR, Enum, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import config

# MySQL 连接字符串
DB_URL = f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}@{config.DB_CONFIG['host']}:{config.DB_CONFIG['port']}/{config.DB_CONFIG['database']}?charset={config.DB_CONFIG['charset']}"

# 数据库引擎
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ====================== 11 张表 严格对应你的结构 ======================
# 1. 成就类型表
class AchievementTypes(Base):
    __tablename__ = "achievement_types"
    achievement_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    description = Column(Text)
    icon_url = Column(String(255))

# 2. 每日答题表
class DailyQuiz(Base):
    __tablename__ = "daily_quiz"
    quiz_id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text)
    option_a = Column(String(255))
    option_b = Column(String(255))
    option_c = Column(String(255))
    option_d = Column(String(255))
    correct_answer = Column(CHAR(1))
    explanation = Column(Text)

# 4. 投放记录表
class DisposalRecords(Base):
    __tablename__ = "disposal_records"
    record_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    category_id = Column(Integer)
    garbage_name = Column(String(255))
    timestamp = Column(DateTime, default=datetime.datetime.now)

# 5. 收藏表
class Favorites(Base):
    __tablename__ = "favorites"
    favorite_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    item_id = Column(Integer)
    item_type = Column(Enum('article', 'example'))
    created_at = Column(DateTime, default=datetime.datetime.now)

# 6. 垃圾分类表
class GarbageCategories(Base):
    __tablename__ = "garbage_categories"
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20))
    color = Column(String(10))
    description = Column(Text)

# 7. 知识文章表
class KnowledgeArticles(Base):
    __tablename__ = "knowledge_articles"
    article_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200))
    content = Column(Text)
    category_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.now)

# 8. 搜索历史表
class SearchHistory(Base):
    __tablename__ = "search_history"
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    search_query = Column(String(255))
    timestamp = Column(DateTime, default=datetime.datetime.now)

# 9. 用户成就表
class UserAchievements(Base):
    __tablename__ = "user_achievements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    achievement_id = Column(Integer)
    unlock_date = Column(DateTime, default=datetime.datetime.now)

# 10. 用户资料表
class UserProfiles(Base):
    __tablename__ = "user_profiles"
    user_id = Column(Integer, primary_key=True)
    level = Column(Integer)
    avatar_url = Column(String(255))
    bio = Column(Text)
    total_points = Column(Integer)
    rank_score = Column(Integer)

# 11. 用户表
class Users(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50))
    password_hash = Column(String(255))
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.now)

# 【缺失的表】垃圾示例表（塑料瓶、电池、果皮等都在这里）
class GarbageExamples(Base):
    __tablename__ = "garbage_examples"
    example_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer)
    name = Column(String(100))
    tips = Column(Text)

# 初始化数据库（连接你已建好的表）
def init_db():
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()