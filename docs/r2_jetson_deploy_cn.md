# R2 夹爪视觉 Jetson 最小部署说明

## 1. Jetson 上要复制的内容

最小运行需要这些目录和文件：

```text
head_rack_align/
configs/r2_gripper.yaml
models/rack_connector_v5_single_slot_best.pt
tools/run_r2_gripper_v5_jetson.sh
requirements.txt
```

如果整包复制，可以直接复制整个 `head_rack_align` 项目目录。不要复制电脑上的 `.venv`，Jetson 要重新建自己的 Python 环境。

## 2. Jetson 上安装依赖

进入项目目录：

```bash
cd /home/jetson/syf/vision_code
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

注意：Jetson 的 PyTorch 和 CUDA 版本跟 JetPack 绑定。如果普通 `pip install` 后 YOLO 不能用 GPU，先用 CPU 跑通接口，再让负责 Jetson 环境的同学安装对应 JetPack 的 PyTorch。

## 3. 确认摄像头编号

插上 USB 摄像头后：

```bash
ls /dev/video*
```

常见情况：

```text
/dev/video0
/dev/video1
```

脚本里的 `CAMERA=0` 对应 `/dev/video0`，`CAMERA=1` 对应 `/dev/video1`。

## 4. Jetson 上运行视觉

不显示窗口，只输出 JSON：

```bash
cd /home/jetson/syf/vision_code
source .venv/bin/activate
CAMERA=0 DEVICE=0 SHOW=0 ./tools/run_r2_gripper_v5_jetson.sh
```

如果 GPU 环境暂时没配好，可以先用 CPU：

```bash
CAMERA=0 DEVICE=cpu SHOW=0 ./tools/run_r2_gripper_v5_jetson.sh
```

需要保存日志：

```bash
CAMERA=0 DEVICE=0 SHOW=0 JSON_OUT=logs/r2_gripper_jetson_test.jsonl ./tools/run_r2_gripper_v5_jetson.sh
```

需要显示调试画面：

```bash
CAMERA=0 DEVICE=0 SHOW=1 ./tools/run_r2_gripper_v5_jetson.sh
```

## 5. 状态机怎么接

状态机把视觉程序当成子进程启动，然后逐行读取 stdout。每一行都是一个 JSON。

核心字段：

```text
status
control_code
target_valid
x_direction
dx_px
confidence
stable_frames
```

第一版动作逻辑：

```python
if control_code == -2:
    forbid_grab()
    search_or_reposition()
elif control_code == 2:
    stop_motion()
    verify_mechanics_then_grab()
elif control_code == 1:
    nudge_right()
elif control_code == -1:
    nudge_left()
else:
    hold_slow()
```

## 6. 重要安全约定

`locked` 不等于马上夹。

`locked` 只代表视觉左右偏差已经稳定进入阈值。状态机还必须确认：

- 当前确实处于取端头流程。
- 夹爪已经打开。
- 底盘或机构已经停稳。
- 高度到位。
- 前后距离或机械限位到位。
- 停稳后继续读取 3 到 5 帧仍然是 `locked`。

满足这些条件后，才允许闭合夹爪。

## 7. 上车后第一轮联调顺序

```text
1. Jetson 能打开摄像头。
2. Jetson 能输出 JSON。
3. 状态机能读到 JSON。
4. 不让机器人动，只看 dx_px 正负是否正确。
5. 只允许低速左右微调，不闭合夹爪。
6. 确认 dx_px 能被修到阈值内。
7. 确认 locked 能稳定出现。
8. 停稳后二次确认 locked。
9. 空夹爪闭合测试。
10. 低速真实夹取测试。
```

## 8. 如果不能识别

视觉输出会变成：

```text
status = search 或 lost
dx_px = null
```

状态机此时必须禁止抓取。可以选择：

- 小范围低速左右搜索。
- 回到机械预定位点重新进入视觉对准。
- 超时后放弃本次取端头。

不要使用旧的 `dx_px` 继续运动或夹取。

