import sys
import os

# 老师小妙招：这行代码能确保 Python 能找到我们刚才写的 backend 文件夹
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_path)

# 现在 Python 就能在根目录找到 backend 文件夹了
from backend.app.agents.trip_planner_agent import create_workflow
from backend.app.agents.trip_planner_agent import create_workflow

def main():
    # 1. 初始化大脑（创建工作流）
    print("🚀 正在初始化 AI 助手...")
    app = create_workflow()

    # 2. 模拟用户的输入
    # 以后这里可以变成从网页或者终端输入的变量
    user_input = {
        "city": "上海",
        "travel_days": 2,
        "weather_info": "", # 初始为空，等专家填
        "attractions": "",
        "final_plan": ""
    }

    # 3. 开启流转！
    print(f"✨ 开始为您的 {user_input['city']} 之旅制定计划...\n")
    
    # 我们使用 invoke 方法来启动图
    result = app.invoke(user_input)

    # 4. 展示最后的笔记本内容
    print("\n" + "="*50)
    print("🎉 您的专属行程单生成完毕！")
    print("="*50)
    print(result["final_plan"])
    print("="*50)

if __name__ == "__main__":
    main()