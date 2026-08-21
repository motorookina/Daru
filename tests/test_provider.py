# 测试模型调用
from daru.core.provider import get_provider

def test_provider_invoke():
    llm = get_provider(provider_name="openai", model_name="deepseek-v4-flash")
    res = llm.invoke("你是谁")
    assert res is not None
    print(res)

if __name__ == "__main__":
    test_provider_invoke()   # 在 PyCharm 里按 F5 直接跑脚本时走这里