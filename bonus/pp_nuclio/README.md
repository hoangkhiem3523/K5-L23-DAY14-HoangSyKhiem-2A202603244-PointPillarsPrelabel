# Bonus Hướng 2 — PointPillars 3D trong CVAT (Nuclio)

Thư mục này chứa Nuclio serverless function `pp-2a202603244` bọc bộ suy luận `vf_pp` (`PointPillars` pre-trained KITTI) để chạy auto-annotation 3D trực tiếp bên trong CVAT local.

## Cấu trúc thư mục
- `function.yaml`: manifest Nuclio (`namespace: nuclio`, `supported_shape_types: cuboid`, đủ 5 nhãn `Car/Truck/Bus/Cyclist/Pedestrian`, `maxRequestBodySize: 33554432`, `eventTimeout: 180s`).
- `main.py`: handler nạp `Detector` một lần trong `init_context`, đọc PCD binary/ASCII từ `body["image"]` (base64), đảo ngược xấp xỉ `intensity` từ kênh `rgb` nén log của `vf_common.intensity_gray`, và trả danh sách cuboid 16 số theo chuẩn CVAT.
- `stage_build.py`: gom ngữ cảnh build tạm tại `out/nuclio_stage_pp/` (đã gitignore) gồm `function.yaml`, `main.py`, `vf_pp/`, `third_party/PointPillars/pointpillars/model/` và trọng số `epoch_160.pth`.
- `eval_nuclio.py`: đọc trực tiếp cuboid từ `GET /api/jobs/<job_id>/annotations` (tránh lỗi export shape `cvat#9144`) và so khớp tâm `<= 0,5 m` cùng nhãn với kết quả chạy offline.

## Lệnh dựng & chạy lại (từ gốc repo)
```bash
# 1. Bật Nuclio cho CVAT Docker (chạy tại thư mục chứa docker-compose.yml của CVAT)
docker compose -f docker-compose.yml -f components/serverless/docker-compose.serverless.yml up -d

# 2. Gom ngữ cảnh build (không commit weights lên Git)
python bonus/pp_nuclio/stage_build.py

# 3. Deploy bằng nuctl 1.16.3 (trên Windows dùng nuctl-linux bên trong container nuclio)
docker cp out/nuclio_stage_pp nuclio:/tmp/nuclio_stage_pp
docker exec nuclio nuctl create project cvat --platform local
docker exec nuclio nuctl deploy --project-name cvat \
  --path /tmp/nuclio_stage_pp --file /tmp/nuclio_stage_pp/function.yaml --platform local

# 4. Gọi auto-annotation 3D qua API CVAT (thay <user>:<pass> và <task_id>)
curl -u <user>:<pass> -H "Content-Type: application/json" \
  -X POST http://localhost:8080/api/lambda/requests \
  -d '{"function": "pp-2a202603244", "task": <task_id>, "threshold": 0.5, "cleanup": true}'

# 5. So khớp với kết quả offline
python bonus/pp_nuclio/eval_nuclio.py --task-id <task_id> \
  --data <Data-VF> --frames d14_2A202603244/frames_B.txt --threshold 0.5
```
