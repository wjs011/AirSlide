# AirSlide

AirSlide 是一个面向课堂汇报和演讲场景的智能演讲辅助 Web 应用。系统通过 Python 后端转换 PPT，通过浏览器摄像头和语音能力完成演示控制原型，适合课程大作业展示和后续扩展。

## 当前功能

- PPT 上传、转换和逐页放映
- 上一页、下一页、全屏、结束演示确认
- 左上角摄像头小窗和人脸状态展示
- 前端摄像头取帧，发送到 Python 后端进行 OpenCV 视觉分析
- 手势滑动触发翻页，带冷却时间和触发阈值，降低误操作
- 空气指针、标注、区域放大模式
- 浏览器语音识别控制：下一页、上一页、指针、标注、放大、暂停、继续、结束演示
- 交互设置面板：冷却时间、滑动阈值、置信阈值、外部 PowerPoint 控制开关
- 可选外部 PowerPoint 控制：Python 优先尝试 PowerPoint COM，失败时使用系统按键兜底

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

## 参考

项目的手势冷却、手势到放映动作映射、PowerPoint COM 优先并用键盘兜底的设计，参考了 MIT 许可证项目：

https://github.com/mohamed-eldagla/gesture-controlled-presentation
