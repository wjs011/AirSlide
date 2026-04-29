# AirSlide

AirSlide 是一个面向课堂汇报和演讲场景的 PPT 放映 Web 应用。当前阶段只实现 PPT 上传、后端转换和前端翻页放映，摄像头、手势识别、语音控制后续再接入。

## 运行后端

```powershell
cd airslide-backend
python -m pip install -r requirements.txt
python -m uvicorn main:socket_app --reload --host 127.0.0.1 --port 8000
```

后端是 Python + FastAPI。上传的 PPT 会保存到 `airslide-backend/storage/`，并转换成逐页可访问的放映画面。

在 Windows 且安装了 PowerPoint 时，后端会优先调用 PowerPoint 导出高清图片；如果导出不可用，会从 `.pptx` 中提取文字生成预览页，保证放映流程可以跑通。

## 运行前端

```powershell
npm install
npm run dev
```

前端默认通过 Vite 代理访问 `http://127.0.0.1:8000` 的后端接口。打开终端中显示的本地地址后，上传 `.ppt` 或 `.pptx` 文件即可开始放映。

## 快捷键

- `←` / `PageUp`：上一页
- `→` / `PageDown` / `Space`：下一页
- `Home`：第一页
- `End`：最后一页
- `F`：全屏放映
