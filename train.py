from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("yolov8n-cls.pt")
    model.train(
        data="dataset",
        epochs=50,
        imgsz=224,
        batch=8,
        name="train8"  # 这次会生成 train8 文件夹
    )