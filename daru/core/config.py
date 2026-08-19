import os

from dotenv import load_dotenv

load_dotenv()

CORE_DIR=os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR=os.path.dirname(CORE_DIR)
PROJECT_ROOT_DIR=os.path.dirname(PACKAGE_DIR)

WORKSPACE_DIR=os.path.join(PROJECT_ROOT_DIR,"workspace")
DB_PATH=os.path.join(WORKSPACE_DIR,"state.sqlite3")
MEMORY_DIR=os.path.join(WORKSPACE_DIR,"memory")
PERSONA_DIR=os.path.join(WORKSPACE_DIR,"persona")
SCRIPTS_DIR=os.path.join(WORKSPACE_DIR,"scripts")
OFFICE_DIR=os.path.join(WORKSPACE_DIR,"office")
SKILL_DIR=os.path.join(WORKSPACE_DIR,"skill")
TASK_FILE=os.path.join(WORKSPACE_DIR,"task.json")

for dir in [WORKSPACE_DIR,MEMORY_DIR,PERSONA_DIR,SCRIPTS_DIR,OFFICE_DIR,SKILL_DIR]:
    os.makedirs(dir,exist_ok=True)

print(f"[CONFIG] {WORKSPACE_DIR}路径已就绪!")