# EDBO+ HTTP 服务前端对接说明

本文档说明 Web 前端如何调用 EDBO+ 贝叶斯优化 HTTP 服务。

## 启动服务

在项目根目录执行：

```bash
conda activate edbo_env
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务启动后可访问：

```http
GET http://localhost:8000/health
```

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok"
  }
}
```

## 统一响应格式

所有接口都返回同一层业务包装：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

约定：

- `code = 0` 表示成功。
- `code != 0` 表示业务失败或参数错误。
- 算法结果、任务状态等内容都放在 `data` 中。

常见错误码：

- `40001`：请求参数校验失败。
- `40401`：任务不存在。
- `40901`：任务尚未完成，暂时不能获取结果。
- `50001`：算法执行失败。

## 接口列表

```http
POST /api/v1/edbo/tasks
GET  /api/v1/edbo/tasks/{task_id}
GET  /api/v1/edbo/tasks/{task_id}/result
```

推荐调用流程：

1. 前端调用 `POST /api/v1/edbo/tasks` 提交任务。
2. 后端立即返回 `task_id`。
3. 前端每 2 秒调用 `GET /api/v1/edbo/tasks/{task_id}` 查询状态。
4. 状态为 `completed` 后调用 `GET /api/v1/edbo/tasks/{task_id}/result` 获取结果。

## 提交优化任务

```http
POST /api/v1/edbo/tasks
Content-Type: application/json
```

请求示例：

```json
{
  "task_id": "electrochemistry_round1",
  "batch": 3,
  "seed": 1,
  "columns_features": "all",
  "init_sampling_method": "cvt",
  "objectives": [
    {
      "name": "yield_percent",
      "mode": "max"
    },
    {
      "name": "selectivity_percent",
      "mode": "max"
    },
    {
      "name": "charge_F_per_mol",
      "mode": "min"
    }
  ],
  "candidates": [
    {
      "candidate_id": "rxn_0001",
      "fluorenone_mmol": 1.0,
      "catalyst": "4-hydroxy-TEMPO",
      "catalyst_loading_mol_pct": 10,
      "electrolyte": "n-Bu4NBF4",
      "electrolyte_equiv": 0.1,
      "PPh3_equiv": 1.0,
      "benzyl_alcohol_equiv": 1.5,
      "solvent_ratio": "MeCN:EtOAc=5:5",
      "solvent_total_mL": 10.0,
      "yield_percent": 68.4,
      "selectivity_percent": 72.1,
      "charge_F_per_mol": 1.58
    },
    {
      "candidate_id": "rxn_0002",
      "fluorenone_mmol": 1.0,
      "catalyst": "TEMPO",
      "catalyst_loading_mol_pct": 15,
      "electrolyte": "Et4NBF4",
      "electrolyte_equiv": 0.2,
      "PPh3_equiv": 1.0,
      "benzyl_alcohol_equiv": 2.0,
      "solvent_ratio": "MeCN:EtOAc=4:6",
      "solvent_total_mL": 10.0,
      "yield_percent": 62.7,
      "selectivity_percent": 69.5,
      "charge_F_per_mol": 1.82
    },
    {
      "candidate_id": "rxn_0003",
      "fluorenone_mmol": 1.0,
      "catalyst": "ABNO",
      "catalyst_loading_mol_pct": 10,
      "electrolyte": "n-Bu4NPF6",
      "electrolyte_equiv": 0.1,
      "PPh3_equiv": 1.5,
      "benzyl_alcohol_equiv": 1.5,
      "solvent_ratio": "MeCN:EtOAc=6:4",
      "solvent_total_mL": 10.0,
      "yield_percent": 74.2,
      "selectivity_percent": 78.8,
      "charge_F_per_mol": 1.43
    },
    {
      "candidate_id": "rxn_0004",
      "fluorenone_mmol": 1.0,
      "catalyst": "4-acetamido-TEMPO",
      "catalyst_loading_mol_pct": 20,
      "electrolyte": "n-Bu4NBF4",
      "electrolyte_equiv": 0.2,
      "PPh3_equiv": 1.5,
      "benzyl_alcohol_equiv": 2.0,
      "solvent_ratio": "MeCN:EtOAc=7:3",
      "solvent_total_mL": 10.0,
      "yield_percent": 70.1,
      "selectivity_percent": 75.4,
      "charge_F_per_mol": 1.65
    },
    {
      "candidate_id": "rxn_0005",
      "fluorenone_mmol": 1.0,
      "catalyst": "4-hydroxy-TEMPO",
      "catalyst_loading_mol_pct": 15,
      "electrolyte": "Et4NBF4",
      "electrolyte_equiv": 0.1,
      "PPh3_equiv": 1.0,
      "benzyl_alcohol_equiv": 2.5,
      "solvent_ratio": "MeCN:EtOAc=5:5",
      "solvent_total_mL": 10.0,
      "yield_percent": null,
      "selectivity_percent": null,
      "charge_F_per_mol": null
    },
    {
      "candidate_id": "rxn_0006",
      "fluorenone_mmol": 1.0,
      "catalyst": "ABNO",
      "catalyst_loading_mol_pct": 15,
      "electrolyte": "n-Bu4NBF4",
      "electrolyte_equiv": 0.2,
      "PPh3_equiv": 1.0,
      "benzyl_alcohol_equiv": 1.5,
      "solvent_ratio": "MeCN:EtOAc=4:6",
      "solvent_total_mL": 10.0,
      "yield_percent": null,
      "selectivity_percent": null,
      "charge_F_per_mol": null
    },
    {
      "candidate_id": "rxn_0007",
      "fluorenone_mmol": 1.0,
      "catalyst": "TEMPO",
      "catalyst_loading_mol_pct": 10,
      "electrolyte": "n-Bu4NPF6",
      "electrolyte_equiv": 0.2,
      "PPh3_equiv": 1.5,
      "benzyl_alcohol_equiv": 2.0,
      "solvent_ratio": "MeCN:EtOAc=6:4",
      "solvent_total_mL": 10.0,
      "yield_percent": null,
      "selectivity_percent": null,
      "charge_F_per_mol": null
    },
    {
      "candidate_id": "rxn_0008",
      "fluorenone_mmol": 1.0,
      "catalyst": "4-acetamido-TEMPO",
      "catalyst_loading_mol_pct": 15,
      "electrolyte": "Et4NBF4",
      "electrolyte_equiv": 0.1,
      "PPh3_equiv": 1.5,
      "benzyl_alcohol_equiv": 2.5,
      "solvent_ratio": "MeCN:EtOAc=7:3",
      "solvent_total_mL": 10.0,
      "yield_percent": null,
      "selectivity_percent": null,
      "charge_F_per_mol": null
    }
  ],
  "include_predictions": true
}
```

提交成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10",
    "status": "pending",
    "status_url": "/api/v1/edbo/tasks/9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10",
    "result_url": "/api/v1/edbo/tasks/9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10/result"
  }
}
```

字段说明：

- `task_id`：可选，前端业务侧任务名。后端仍会生成一个真正用于查询的 UUID。
- `batch`：本轮推荐实验数量。
- `seed`：随机种子。
- `columns_features`：推荐传 `"all"`；后端会自动排除目标列、`priority` 和 `candidate_id`。
- `init_sampling_method`：首轮采样方法，可选 `random`、`lhs`、`cvt`。
- `objectives`：动态目标列表，`mode` 只能是 `max` 或 `min`。
- `candidates`：完整候选实验空间，已实验目标填数字，未实验目标填 `null`。
- `include_predictions`：是否在结果中返回预测均值、标准差和期望改进。

## 查询任务状态

```http
GET /api/v1/edbo/tasks/{task_id}
```

计算中：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10",
    "status": "processing",
    "progress": null
  }
}
```

完成：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10",
    "status": "completed",
    "progress": null,
    "result_url": "/api/v1/edbo/tasks/9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10/result"
  }
}
```

失败：

```json
{
  "code": 50001,
  "message": "EDBO optimization failed: not enough observed experiments",
  "data": {
    "task_id": "9c7a4c5e-5a4c-4c8a-8c42-9f6d5e1c2b10",
    "status": "failed"
  }
}
```

## 获取算法结果

```http
GET /api/v1/edbo/tasks/{task_id}/result
```

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "electrochemistry_round0",
    "status": "completed",
    "batch": 8,
    "recommended_count": 8,
    "recommendations": [
      {
        "rank": 1,
        "candidate_id": "rxn_0002",
        "priority": 1.0,
        "conditions": {
          "fluorenone_mmol": 1.0,
          "catalyst": "TEMPO",
          "catalyst_loading_mol_pct": 15,
          "electrolyte": "Et4NBF4",
          "electrolyte_equiv": 0.2,
          "PPh3_equiv": 1.0,
          "benzyl_alcohol_equiv": 2.0,
          "solvent_ratio": "MeCN:EtOAc=4:6",
          "solvent_total_mL": 10.0
        },
        "predictions": {
          "yield_percent": {
            "predicted_mean": 59.62,
            "predicted_std_dev": 14.25,
            "expected_improvement": 2.77
          }
        }
      }
    ],
    "artifacts": {
      "input_csv": "input.csv",
      "result_csv": "input.csv",
      "prediction_csv": "pred_input.csv"
    }
  }
}
```

说明：

- `recommendations` 只返回 `priority == 1` 的推荐实验。
- `conditions` 是实验条件，不包含目标值、预测字段、`priority` 和 `candidate_id`。
- `predictions` 仅在已有历史观测并且生成 `pred_input.csv` 时返回。
- 首轮所有目标都是 `null` 时，服务会自动进入初始化采样，此时通常没有 `predictions`。

## 前端轮询示例

```javascript
async function submitEdboTask(payload) {
  const submitRes = await fetch("http://localhost:8000/api/v1/edbo/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const submitBody = await submitRes.json();
  if (submitBody.code !== 0) {
    throw new Error(submitBody.message);
  }

  return submitBody.data;
}

async function pollEdboResult(taskId) {
  const maxAttempts = 60;
  const intervalMs = 2000;

  for (let i = 0; i < maxAttempts; i += 1) {
    const statusRes = await fetch(`http://localhost:8000/api/v1/edbo/tasks/${taskId}`);
    const statusBody = await statusRes.json();

    if (statusBody.code !== 0) {
      throw new Error(statusBody.message);
    }

    if (statusBody.data.status === "completed") {
      const resultRes = await fetch(`http://localhost:8000/api/v1/edbo/tasks/${taskId}/result`);
      const resultBody = await resultRes.json();
      if (resultBody.code !== 0) {
        throw new Error(resultBody.message);
      }
      return resultBody.data;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error("EDBO task timeout");
}

async function runEdbo(payload) {
  const task = await submitEdboTask(payload);
  return pollEdboResult(task.task_id);
}
```

## 部署配置

可通过环境变量调整：

```bash
EDBO_WORK_ROOT=runtime/edbo_tasks
EDBO_MAX_WORKERS=2
EDBO_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

生产环境建议：

- 使用 Redis 或数据库保存任务状态，避免服务重启后任务丢失。
- 使用 Celery/RQ 替代本地线程池，控制并发和队列长度。
- 给接口增加 API Key 或 JWT 鉴权。
- 如果候选空间很大，不要一次返回完整预测表，推荐改成分页接口或文件下载。
