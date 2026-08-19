"""
    测试config.py，主要进行导入测试
"""
import unittest

class TestConfig(unittest.TestCase):
    def test_config_import(self):
        """测试配置模块导入"""
        from daru.core.config import WORKSPACE_DIR,MEMORY_DIR,PERSONA_DIR,SCRIPTS_DIR,OFFICE_DIR,SKILL_DIR,DB_PATH,TASK_FILE

        # 验证配置项存在
        self.assertIsInstance(WORKSPACE_DIR,str)
        self.assertIsInstance(MEMORY_DIR,str)
        self.assertIsInstance(PERSONA_DIR,str)
        self.assertIsInstance(SCRIPTS_DIR,str)
        self.assertIsInstance(OFFICE_DIR,str)
        self.assertIsInstance(SKILL_DIR,str)
        self.assertIsInstance(DB_PATH,str)
        self.assertIsInstance(TASK_FILE,str)

if __name__ == '__main__':
    unittest.main()