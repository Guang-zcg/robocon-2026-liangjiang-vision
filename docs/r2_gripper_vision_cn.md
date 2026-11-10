# R2 夹爪视觉修正当前方案

## 当前目标

视觉模块只负责夹爪左右修正，不负责完整抓取决策。

```text
摄像头看到快接头/连接部位
YOLOv8 检测 rack_connector
计算目标中心相对夹爪基准点的 dx_px
状态机根据 dx_px 小步左右修正
连续稳定后输出 locked
```

第一版只闭环 `x` 方向。高度和前后距离暂时交给机械限位、预定位或固定动作。

## 当前主模型

```text
models\rack_connector_v5_single_slot_best.pt
```

训练数据包含：

- `rack_connector_with_head`：中远距离/带端头示意数据。
- `near_gripper_connector`：夹爪近距离裸转接口数据。
- `near_gripper_spear_occlusion`：夹爪视角下矛头遮挡转接口数据。

当前模型已经验证：

- 近距离夹爪视角能检测转接口。
- 目标在左侧时 `dx_px < 0`，目标在右侧时 `dx_px > 0`。
- 矛头遮挡时，只要连接部位可见，仍能输出有效 `dx_px`。

尚未完成：

- 摄像头最终安装位标定。
- 掌/拳遮挡数据。
- 真实端头架和比赛场地验证。
- Jetson 与 R2 状态机联调。

## 电脑端测试命令

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
$env:PYTHONPATH = (Get-Location).Path
python -m head_rack_align.app --model "models\rack_connector_v5_single_slot_best.pt" --camera 1 --draw-detections --show --config configs\r2_gripper.yaml
```

或使用脚本：

```powershell
.\tools\run_r2_gripper_v3.ps1
```

窗口显示含义：

- 紫色框：YOLO 原始检测框。
- 蓝/红点：视觉模块选中的控制目标中心。
- 黄色十字：夹爪抓取基准点。
- `dx`：目标中心 x 减去黄色十字 x。

## 输出给状态机

每帧输出一行 JSON，例如：

```json
{"status":"tracking","target_slot":1,"target_type":"rack_connector","dx_px":-42.1,"dy_px":-38.5,"confidence":0.86,"stable_frames":0,"timestamp_ms":123456,"angle_deg":null,"detected_slots":1,"alignment_axes":"x","message":"single_target"}
```

状态机建议：

- `tracking`：目标可见，但偏差未进阈值；按 `dx_px` 小步左右修正。
- `aligned`：偏差进入阈值，但稳定帧数不足；继续慢速保持。
- `locked`：连续稳定，允许执行抓取动作。
- `search`/`lost`：不要抓取，回到搜索或重新预定位。

第一版控制含义：

```text
dx_px > 0：目标在夹爪基准点右侧，R2/夹爪向右修正。
dx_px < 0：目标在夹爪基准点左侧，R2/夹爪向左修正。
```

当前推荐的联调方式：

1. 视觉程序作为独立进程运行。
2. 每帧从标准输出读取一行 JSON。
3. 状态机只使用 `status`、`dx_px`、`confidence`、`stable_frames`。

最小伪代码：

```python
if status in ("search", "lost"):
    stop_grab()
    search_or_reposition()
elif status == "locked":
    stop_motion()
    grab()
elif dx_px > deadband:
    nudge_right()
elif dx_px < -deadband:
    nudge_left()
else:
    hold_slow()
```

读取示例：

```powershell
python tools\state_machine_reader_demo.py --camera 1 --show
```

如果需要把 JSON 同时保存成日志：

```powershell
python -m head_rack_align.app --model "models\rack_connector_v5_single_slot_best.pt" --camera 1 --config configs\r2_gripper.yaml --json-out logs\r2_vision.jsonl
```

## 上车前必须做

1. 固定摄像头安装位置。
2. 重新标定黄色十字：

   ```powershell
   python tools\pick_grab_center.py --camera 1
   ```

3. 把输出的 `grab_center_x/y` 写入 `configs\r2_gripper.yaml`。
4. 用真实夹爪动作验证 `dx_px` 正负方向和底盘/机构修正方向一致。
5. 根据实机抖动把 `align_threshold_px` 从测试值逐步收紧。

## 后续数据补充

优先补：

- 掌遮挡转接口。
- 拳遮挡转接口。
- 真实端头架上的多槽位视角。
- 比赛场地灯光下的灰色实物。

如果误检明显，补负样本：

- 没有转接口的红色夹爪。
- 地面、线缆、黑色键盘、灰色/白色背景。
- 人手、衣服、场地线。

