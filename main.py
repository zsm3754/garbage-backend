from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import uuid
import random
from datetime import date
import config
import models
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO


app = FastAPI(title="垃圾分类APP")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
AVATAR_DIR = "avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=AVATAR_DIR), name="avatars")
model = YOLO("runs/classify/train82/weights/best.pt")
# ------------------------------
# AI 识别函数
# ------------------------------
def yolo_recognize_image(image_path: str):
    try:
        results = model(image_path)
        detect_items = []

        for result in results:
            if hasattr(result, 'probs') and result.probs is not None:
                top1_idx = result.probs.top1
                conf = float(result.probs.top1conf)
                class_name = result.names[top1_idx]
                detect_items.append({
                    "item": class_name,
                    "confidence": round(conf, 2)
                })
            elif hasattr(result, 'boxes') and result.boxes is not None:
                for box in result.boxes:
                    class_name = model.names[int(box.cls[0])]
                    confidence = round(float(box.conf[0]), 2)
                    detect_items.append({"item": class_name, "confidence": confidence})

        return detect_items if detect_items else [{"item": "未识别", "confidence": 0.0}]
    except Exception as e:
        print("识别错误：", e)
        return [{"item": "识别失败", "confidence": 0.0}]

# ------------------------------
# AI拍照识别接口
# ------------------------------
@app.post("/api/garbage/recognize")
async def recognize(file: UploadFile = File(...)):
    filename = f"{uuid.uuid4()}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(await file.read())
    res = yolo_recognize_image(path)
    return {"code": 200, "data": res}

@app.on_event("startup")
def startup():
    models.init_db()
    print("✅ 数据库连接成功")

# ------------------------------
# 用户注册
# ------------------------------
class UserRegister(BaseModel):
    username: str
    password: str
    email: str = None

@app.post("/api/user/register")
def register(user: UserRegister, db: Session = Depends(models.get_db)):
    exists = db.query(models.Users).filter(models.Users.username == user.username).first()
    if exists:
        raise HTTPException(400, "用户名已存在")

    new_user = models.Users(
        username=user.username,
        password_hash=user.password,
        email=user.email
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # ========== 新增：自动创建 user_profiles ==========
    new_profile = models.UserProfiles(
        user_id=new_user.user_id,
        total_points=0,
        avatar_url=None
    )
    db.add(new_profile)
    db.commit()

    return {"code": 200, "msg": "注册成功"}

# ------------------------------
# 用户登录
# ------------------------------
class UserLogin(BaseModel):
    username: str
    password: str

@app.post("/api/user/login")
def login(user: UserLogin, db: Session = Depends(models.get_db)):
    u = db.query(models.Users).filter(models.Users.username == user.username).first()
    if not u or u.password_hash != user.password:
        raise HTTPException(401, "账号或密码错误")
    return {"code": 200, "msg": "登录成功", "data": {"user_id": u.user_id}}

# ------------------------------
# 每日一题
# ------------------------------
@app.get("/api/quiz/today")
def today_quiz(db: Session = Depends(models.get_db)):
    all_quizzes = db.query(models.DailyQuiz).all()
    if not all_quizzes:
        raise HTTPException(404, "暂无题目")

    today = date.today()
    random.seed(today.toordinal())
    quiz = random.choice(all_quizzes)

    return {
        "code": 200,
        "date": str(today),
        "data": quiz
    }

# ------------------------------
# 提交答题 用标准UPDATE，触发数据库自动逻辑
# ------------------------------
class QuizAnswer(BaseModel):
    user_id: int
    quiz_id: int
    answer: str

@app.post("/api/quiz/submit")
def submit(data: QuizAnswer, db: Session = Depends(models.get_db)):
    quiz = db.query(models.DailyQuiz).filter(models.DailyQuiz.quiz_id == data.quiz_id).first()
    if not quiz:
        raise HTTPException(404, "题目不存在")

    correct = data.answer.strip().upper() == quiz.correct_answer.strip().upper()
    if correct:
        db.query(models.UserProfiles).filter(models.UserProfiles.user_id == data.user_id).update({
            "total_points": models.UserProfiles.total_points + 10
        })
        db.commit()

    return {
        "code": 200,
        "data": {
            "correct": correct,
            "correct_answer": quiz.correct_answer,
            "explanation": quiz.explanation
        }
    }

# ------------------------------
# 搜索历史 结构体
# ------------------------------
class SearchHistoryIn(BaseModel):
    user_id: int
    search_query: str

# ------------------------------
# ✅ 添加搜索历史
# ------------------------------
@app.post("/api/search/history/add")
def add_search_history(data: SearchHistoryIn, db: Session = Depends(models.get_db)):
    if not data.search_query or data.search_query.strip() == "":
        return {"code": 400, "msg": "搜索内容不能为空"}

    new_history = models.SearchHistory(
        user_id=data.user_id,
        search_query=data.search_query.strip()
    )
    db.add(new_history)
    db.commit()
    return {"code": 200, "msg": "搜索历史已保存"}

# ------------------------------
# 文字搜索
# ------------------------------
@app.get("/api/search/keyword")
def search_keyword(keyword: str,db: Session = Depends(models.get_db)):
    try:
        examples = db.query(models.GarbageExamples).filter(
            models.GarbageExamples.name.like(f"%{keyword}%")
        ).all()

        data = []
        for example in examples:
            category = db.query(models.GarbageCategories).filter(
                models.GarbageCategories.category_id == example.category_id
            ).first()

            data.append({
                "name": example.name,
                "category": category.name if category else "未知分类",
                "tips": example.tips if example.tips else "暂无处理建议",
                "example_id": example.example_id
            })

        return {"code": 200, "data": data}

    except Exception as e:
        print(f"搜索错误：{str(e)}")
        return {"code": 500, "data": []}

# ------------------------------
# 用户排名
# ------------------------------
@app.get("/api/rank/user/{user_id}")
def get_user_rank(user_id: int, db: Session = Depends(models.get_db)):
    try:
        profile = db.query(models.UserProfiles).filter(models.UserProfiles.user_id == user_id).first()
        if not profile:
            return {"code": 200, "data": {"rank": 999, "total_points": 0}}

        total_higher = db.query(models.UserProfiles).filter(models.UserProfiles.total_points > profile.total_points).count()
        my_rank = total_higher + 1

        return {
            "code": 200,
            "data": {
                "user_id": user_id,
                "total_points": profile.total_points,
                "rank": my_rank
            }
        }
    except Exception as e:
        print(e)
        return {"code": 200, "data": {"rank": 999, "total_points": 0}}

# ------------------------------
# 投放记录【已改：使用标准UPDATE，触发数据库自动逻辑】
# ------------------------------
class DisposeRecordIn(BaseModel):
    user_id: int
    category_id: int
    garbage_name: str
    is_correct: bool

@app.post("/api/record/add")
def add_dispose_record(data: DisposeRecordIn, db: Session = Depends(models.get_db)):
    try:
        record = models.DisposalRecords(
            user_id=data.user_id,
            category_id=data.category_id,
            garbage_name=data.garbage_name,
        )
        db.add(record)

        added_points = 0
        if data.is_correct:
            db.query(models.UserProfiles).filter(models.UserProfiles.user_id == data.user_id).update({
                "total_points": models.UserProfiles.total_points + 5
            })
            added_points = 5

        db.commit()
        return {"code": 200, "msg": "投放成功", "point": added_points}

    except Exception as e:
        print("报错：", e)
        db.rollback()
        return {"code": 500, "msg": "投放失败"}

# ------------------------------
# 调用存储过程-获取用户成就
# ------------------------------
@app.get("/api/achievement/list/{user_id}")
def get_achievement_list(user_id: int, db: Session = Depends(models.get_db)):
    try:
        cursor = db.connection().cursor()
        cursor.callproc("get_user_achievements", (user_id,))
        res = cursor.fetchall()
        return {"code": 200, "data": res}
    except Exception as e:
        print(e)
        return {"code": 500, "data": []}

# ------------------------------
# 调用存储过程-获取投放次数
# ------------------------------
@app.get("/api/disposal/count/{user_id}")
def disposal_count(user_id: int, db: Session = Depends(models.get_db)):
    try:
        cursor = db.connection().cursor()
        cursor.callproc("get_user_disposal_count", (user_id, 0))
        cnt = cursor.fetchone()[0]
        return {"code": 200, "count": cnt}
    except Exception as e:
        print(e)
        return {"code": 500, "count": 0}

# ------------------------------
# 搜索历史 查询 / 删除 / 清空
# ------------------------------
@app.get("/api/search/history/{user_id}")
def get_search_history(user_id: int, db: Session = Depends(models.get_db)):
    res = db.query(models.SearchHistory).filter(models.SearchHistory.user_id == user_id).all()
    return {"code": 200, "data": res}

@app.delete("/api/search/history/{history_id}")
def delete_search_history(history_id: int, db: Session = Depends(models.get_db)):
    history = db.query(models.SearchHistory).filter(models.SearchHistory.history_id == history_id).first()
    if not history:
        raise HTTPException(404, "记录不存在")
    db.delete(history)
    db.commit()
    return {"code": 200, "msg": "删除成功"}

@app.delete("/api/search/history/clear/{user_id}")
def clear_all_search_history(user_id: int, db: Session = Depends(models.get_db)):
    db.query(models.SearchHistory).filter(models.SearchHistory.user_id == user_id).delete()
    db.commit()
    return {"code": 200, "msg": "清空成功"}

# ------------------------------
# 基础全表接口
# ------------------------------
@app.get("/api/category/all")
def all_category(db: Session = Depends(models.get_db)):
    return {"code": 200, "data": db.query(models.GarbageCategories).all()}

@app.get("/api/user/{user_id}")
def get_user(user_id: int, db: Session = Depends(models.get_db)):
    return {"code": 200, "data": db.query(models.Users).get(user_id)}

@app.get("/api/profile/{user_id}")
def get_profile(user_id: int, db: Session = Depends(models.get_db)):
    return {"code": 200, "data": db.query(models.UserProfiles).filter_by(user_id=user_id).first()}

@app.get("/api/record/list/{user_id}")
def records(user_id: int, db: Session = Depends(models.get_db)):
    return {"code": 200, "data": db.query(models.DisposalRecords).filter_by(user_id=user_id).all()}


@app.get("/api/fav/list/{user_id}")
def favs(user_id: int, db: Session = Depends(models.get_db)):
    favorites = db.query(models.Favorites).filter(models.Favorites.user_id == user_id).all()

    result = []
    for fav in favorites:
        if fav.item_type == 'article':
            article = db.query(models.KnowledgeArticles).filter(
                models.KnowledgeArticles.article_id == fav.item_id
            ).first()
            if article:
                result.append({
                    "favorite_id": fav.favorite_id,
                    "user_id": fav.user_id,
                    "item_id": fav.item_id,
                    "item_type": fav.item_type,
                    "title": article.title,
                    "content": article.content,
                    "category_id": article.category_id,
                    "created_at": fav.created_at
                })
        elif fav.item_type == 'example':
            example = db.query(models.GarbageExamples).filter(
                models.GarbageExamples.example_id == fav.item_id
            ).first()
            if example:
                result.append({
                    "favorite_id": fav.favorite_id,
                    "user_id": fav.user_id,
                    "item_id": fav.item_id,
                    "item_type": fav.item_type,
                    "name": example.name,
                    "tips": example.tips,
                    "created_at": fav.created_at
                })

    return {"code": 200, "data": result}
# ------------------------------
# 文章推荐
# ------------------------------
@app.get("/api/article/recommend")
def recommend_articles(
        category_id: int = None,
        count: int = None,  # 改成 None，允许不传
        db: Session = Depends(models.get_db)
):
    try:
        query = db.query(models.KnowledgeArticles)
        if category_id:
            query = query.filter(models.KnowledgeArticles.category_id == category_id)

        articles = query.order_by(models.KnowledgeArticles.created_at.desc()).all()
        if not category_id:
            random.shuffle(articles)

        # 如果 count 为 None，默认返回 6 条
        take = count if count is not None else 6
        result = articles[:take]

        # 转换成字典格式
        data = []
        for article in result:
            data.append({
                "article_id": article.article_id,
                "title": article.title,
                "content": article.content,
                "category_id": article.category_id,
                "created_at": article.created_at.isoformat() if article.created_at else None
            })

        return {"code": 200, "data": data}
    except Exception as e:
        print(e)
        return {"code": 500, "msg": "获取推荐失败", "data": []}
# ------------------------------
# 获取单篇文章详情
# ------------------------------
@app.get("/api/article/{article_id}")
def get_article(article_id: int, db: Session = Depends(models.get_db)):
    """获取单篇文章的完整内容"""
    article = db.query(models.KnowledgeArticles).filter(
        models.KnowledgeArticles.article_id == article_id
    ).first()

    if not article:
        return {"code": 404, "msg": "文章不存在", "data": None}

    return {
        "code": 200,
        "data": {
            "article_id": article.article_id,
            "title": article.title,
            "content": article.content,
            "summary": getattr(article, 'summary', ''),
            "category_id": article.category_id,
            "created_at": article.created_at.isoformat() if article.created_at else None
        }
    }



@app.get("/api/achievement/types")
def achievements(db: Session = Depends(models.get_db)):
    return {"code": 200, "data": db.query(models.AchievementTypes).all()}

# ------------------------------
# 更换用户名
# ------------------------------
class UpdateUsername(BaseModel):
    user_id: int
    password: str
    new_username: str

@app.post("/api/user/update/username")
def update_username(data: UpdateUsername, db: Session = Depends(models.get_db)):
    user = db.query(models.Users).filter(models.Users.user_id == data.user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    if user.password_hash.strip() != data.password.strip():
        raise HTTPException(403, "密码错误，请输入登录密码")

    exists = db.query(models.Users).filter(
        models.Users.username == data.new_username,
        models.Users.user_id != data.user_id
    ).first()
    if exists:
        raise HTTPException(400, "用户名已被使用")

    user.username = data.new_username
    db.commit()
    return {"code": 200, "msg": "用户名修改成功"}

# ------------------------------
# 上传头像
# ------------------------------


@app.post("/api/user/upload/avatar")
async def upload_avatar(
    user_id: int,
    password: str,
    file: UploadFile = File(...),
    db: Session = Depends(models.get_db)
):
    user = db.query(models.Users).filter(models.Users.user_id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    if user.password_hash.strip() != password.strip():
        raise HTTPException(403, "密码错误，无法修改头像")

    profile = db.query(models.UserProfiles).filter(models.UserProfiles.user_id == user_id).first()
    if not profile:
        raise HTTPException(404, "用户资料不存在")

    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    avatar_filename = f"avatar_{user_id}_{uuid.uuid4()}.{file_ext}"
    avatar_path = os.path.join(AVATAR_DIR, avatar_filename)

    with open(avatar_path, "wb") as f:
        f.write(await file.read())

    profile.avatar_url = avatar_filename
    db.commit()

    return {
        "code": 200,
        "msg": "头像上传成功",
        "avatar_url": f"/avatars/{avatar_filename}"
    }


# ------------------------------
# 添加收藏
# ------------------------------
class FavoriteAdd(BaseModel):
    user_id: int
    item_id: int
    item_type: str  # 'article' 或 'example'


@app.post("/api/fav/add")
def add_favorite(data: FavoriteAdd, db: Session = Depends(models.get_db)):
    # 检查是否已收藏
    exists = db.query(models.Favorites).filter(
        models.Favorites.user_id == data.user_id,
        models.Favorites.item_id == data.item_id,
        models.Favorites.item_type == data.item_type
    ).first()
    if exists:
        return {"code": 400, "msg": "已经收藏过了"}

    new_fav = models.Favorites(
        user_id=data.user_id,
        item_id=data.item_id,
        item_type=data.item_type
    )
    db.add(new_fav)
    db.commit()
    return {"code": 200, "msg": "收藏成功"}


# ------------------------------
# 取消收藏
# ------------------------------
@app.delete("/api/fav/remove")
def remove_favorite(user_id: int, item_id: int, item_type: str, db: Session = Depends(models.get_db)):
    fav = db.query(models.Favorites).filter(
        models.Favorites.user_id == user_id,
        models.Favorites.item_id == item_id,
        models.Favorites.item_type == item_type
    ).first()
    if not fav:
        raise HTTPException(404, "收藏记录不存在")

    db.delete(fav)
    db.commit()
    return {"code": 200, "msg": "取消收藏成功"}

# ------------------------------
# 启动
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.SERVER_CONFIG["host"],
        port=config.SERVER_CONFIG["port"],
        reload=True
    )