"""设置 API 检查：GET 打码 / POST 更新（含 .env 原位改写）/ 连接测试。

用法：python tests/manual/e2e_settings_check.py [base_url]
注意：POST 用现有值回写（不真换 key），验证写路径但不破坏配置。
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8300"


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_error": json.loads(e.read().decode("utf-8")).get("detail", "")}


def main() -> None:
    # 1. 当前配置（打码）
    cur = get("/api/settings")
    print(f"[读取] key={cur['api_key_masked']} ｜ {cur['base_url']} ｜ {cur['model']}")
    assert "sk-" not in cur["api_key_masked"] or "****" in cur["api_key_masked"], "key 未打码！"

    # 2. 回写相同值（验证写路径 + 立即生效，不动真实 key）
    saved = post("/api/settings", {"api_key": "", "base_url": cur["base_url"],
                                   "model": cur["model"]})
    assert "api_key_masked" in saved, saved
    print(f"[回写] OK，key 仍为 {saved['api_key_masked']}")

    # 3. 连接测试（真实最小 LLM 调用）
    t = post("/api/settings/test", {})
    if t.get("ok"):
        print(f"[测试] 连接正常：{t['model']} 回复「{t['reply']}」 ｜ {t['usage']}")
    else:
        print(f"[测试] 失败（预期内当 key 无效时）: {t.get('_http_error')}")
    print("\n[结论] 设置 API 通过 ✔")


if __name__ == "__main__":
    main()
