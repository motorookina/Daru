## 1.基本说明
LLM 工厂，提供不同模型的适配

## 2.详细设计
### 2.1 初始化
```algoithm
加载环境变量
设置各大厂商官方的OPENAI兼容接口地址，当用户未配置时作为BASE_URL兜底
```

### 2.2 get_provider
```text
Args:
    provider_name：供应商名称
    model_name: 模型名称
    temperature: 模型温度
    base_url: 允许外部传入
    api_key: 允许外部传入
    **kwargs: 其他参数
Return:
    BaseChatModel
Logic:
提供商名称小写
IF 提供商是指定的模型提供商
    THEN 导入ChatOpenAI
    从环境变量中读取当前的OPENAI_API_KEY
    IF key不存在
        THEN 抛出异常ValueError
    从环境变量中读取当前的OPEN_API_BASE_URL
    END IF
    IF base_url不存在
        THEN 从OPENAI兼容接口地址字典中根据提供商名称取出对应的兼容接口地址
    END IF
    RETURN ChatOpenAI对象
ELSE IF 提供商名称为anthropic
    THEN 导入 ChatAnthropic
    获取当前的API_KEY
    IF 当前的key不存在：
        THEN 抛出异常
    取用传入的base_url or 从环境变量中读取
    RETURN ChatAnthropic对象
ELSE IF 提供商为ollama:
    THEN 导入 ChatOllama
    获取base_url
    RETURN ChatOllama对象
ELSE 
    THEN 抛出异常，不支持的模型提供商
```