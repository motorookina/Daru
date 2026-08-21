import os
from langchain_core.language_models.chat_models import BaseChatModel
from dotenv import load_dotenv

'''
多模型适配(Factory)
'''
load_dotenv()

# 各大厂商官方的 OpenAI 兼容接口地址 (当用户未配置 BASE_URL 时作为兜底)
COMPATIBLE_BASE_URLS = {
    "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "z.ai": "https://open.bigmodel.cn/api/paas/v4",
    "tencent": "https://api.hunyuan.cloud.tencent.com/v1",
}

# OPENAI
openai_provider = ["openai", "aliyun", "dashscope", "z.ai", "tencent"]


def get_provider(
        provider_name: str = "openai",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        base_url: str | None = None,
        api_key: str | None = None,
        **kwargs
) -> BaseChatModel:
    """
    获取供应商提供的模型
    :param provider_name: 供应商名称
    :param model_name: 模型名称
    :param temperature: 模型温度
    :param base_url: 模型接口地址
    :param api_key: 模型的key
    :param kwargs: 其他传入参数
    :return: 返回的模型对象
    """
    if provider_name in openai_provider:
        from langchain_openai import ChatOpenAI
        openai_api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError(f"OPENAI_API_KEY不存在.")
        openai_base_url = base_url or os.environ.get("OPENAI_API_BASE_URL")
        if not openai_base_url:
            # 获取各大厂商对OPENAI的兼容URL地址
            openai_base_url = COMPATIBLE_BASE_URLS.get(provider_name)
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=openai_api_key,
            base_url=openai_base_url,
            **kwargs
        )
    elif provider_name == "anthropic":
        from langchain_anthropic import ChatAnthropic
        anthropic_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError(f"ANTHROPIC_API_KEY不存在.")
        anthropic_base_url = base_url or os.environ.get("ANTHROPIC_API_BASE_URL")
        if not anthropic_base_url:
            raise ValueError(f"ANTHROPIC_API_BASE_URL不存在.")
        return ChatAnthropic(
            model_name=model_name,
            temperature=temperature,
            api_key=anthropic_api_key,
            base_url=anthropic_base_url,
            **kwargs
        )
    elif provider_name == "ollama":
        from langchain_community.chat_models import ChatOllama
        ollama_base_url = base_url or os.environ.get("OLLAMA_API_BASE_URL")
        if not ollama_base_url:
            raise ValueError(f"OLLAMA_API_BASE_URL不存在")
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=ollama_base_url,
            **kwargs
        )
    else:
        raise ValueError(f"不支持的模型提供商: {provider_name}")
