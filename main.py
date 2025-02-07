from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
import json
import os
import shutil
from datetime import datetime
import traceback

# 注册插件
@register(name="API一键修改", description="一键修改API配置", version="0.1", author="Assistant")
class KeyConfigPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        self.config_path = "data/config/provider.json"
        self.llm_models_source = "plugins/key/llm-models.json"
        self.llm_models_target = "data/metadata/llm-models.json"
        self.user_states = {}  
        self.host = host
        
    async def initialize(self):
        pass

    def backup_file(self, file_path):
        """创建文件备份"""
        try:
            if os.path.exists(file_path):
                backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                shutil.copy2(file_path, backup_path)
                return backup_path
            return None
        except Exception as e:
            raise

    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        sender_id = ctx.event.sender_id
        
        if msg == "/一键修改api":
            self.user_states[sender_id] = {
                'step': 1,
                'api_url': None,
                'api_key': None,
                'model_name': None
            }
            ctx.add_return("reply", ["步骤1: 请输入API URL\n(通常为网站后面加v1)\n(例如: 官网为https://ai.thelazy.top/ 那么API URL为 https://ai.thelazy.top/v1)"])
            ctx.prevent_default()
            return
            
        if sender_id in self.user_states:
            current_state = self.user_states[sender_id]
            
            if current_state['step'] == 1:  
                if not msg.endswith('/v1'):
                    ctx.add_return("reply", ["API URL格式不正确，请确保以/v1结尾\n例如: https://ai.thelazy.top/v1"])
                    ctx.prevent_default()
                    return
                current_state['api_url'] = msg
                current_state['step'] = 2
                ctx.add_return("reply", ["步骤2: 请输入API Key\n(格式应为: sk-xxxxxxxx)"])
                
            elif current_state['step'] == 2: 
                if not msg.startswith('sk-'):
                    ctx.add_return("reply", ["API Key格式不正确，请重新输入\n(格式应为: sk-xxxxxxxx)"])
                    ctx.prevent_default()
                    return
                current_state['api_key'] = msg.strip()
                current_state['step'] = 3
                ctx.add_return("reply", ["步骤3: 请输入模型名称\n(请输入API网站给的模型价格中的模型名称)"])
                
            elif current_state['step'] == 3:  
                current_state['model_name'] = msg.strip()
                
                try:
                    
                    provider_backup = self.backup_file(self.config_path)
                    llm_models_backup = self.backup_file(self.llm_models_target)

                    
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    
                    config['keys']['openai'] = [current_state['api_key']]
                    config['requester']['openai-chat-completions']['base-url'] = current_state['api_url']
                    config['model'] = f"OneAPI/{current_state['model_name']}"

                    
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except Exception:
                            pass

                    
                    if os.path.exists(self.llm_models_source):
                        with open(self.llm_models_source, 'r', encoding='utf-8') as f:
                            llm_models = json.load(f)
                        
                        
                        model_exists = False
                        for model in llm_models['list']:
                            if model.get('model_name') == current_state['model_name'] or model.get('name') == f"OneAPI/{current_state['model_name']}":
                                model_exists = True
                                break
                        
                        
                        if not model_exists:
                            new_model = {
                                "model_name": current_state['model_name'],
                                "name": f"OneAPI/{current_state['model_name']}",
                                "tool_call_supported": True,
                                "vision_supported": True
                            }
                            llm_models['list'].append(new_model)
                            
                            # 保存更新后的 llm-models.json
                            with open(self.llm_models_source, 'w', encoding='utf-8') as f:
                                json.dump(llm_models, f, indent=4, ensure_ascii=False)
                                f.flush()
                                try:
                                    os.fsync(f.fileno())
                                except Exception:
                                    pass

                    
                    success_msg = ["配置已更新成功！"]
                    if os.path.exists(self.llm_models_source):
                        shutil.copy2(self.llm_models_source, self.llm_models_target)
                        success_msg.extend([
                            "1. API URL已设置为: " + current_state['api_url'],
                            "2. API Key已设置",
                            f"3. 默认模型已更新为: OneAPI/{current_state['model_name']}",
                            "4. llm-models.json已更新" + (" (已添加新模型)" if not model_exists else "")
                        ])
                        if provider_backup:
                            success_msg.append(f"5. provider.json已备份为: {os.path.basename(provider_backup)}")
                        if llm_models_backup:
                            success_msg.append(f"6. llm-models.json已备份为: {os.path.basename(llm_models_backup)}")
                    else:
                        success_msg.extend([
                            "1. API URL已设置为: " + current_state['api_url'],
                            "2. API Key已设置",
                            f"3. 默认模型已更新为: OneAPI/{current_state['model_name']}",
                            "注意：未找到llm-models.json文件，请检查文件是否存在"
                        ])
                        if provider_backup:
                            success_msg.append(f"4. provider.json已备份为: {os.path.basename(provider_backup)}")
                    
                    success_msg.append("\n请按以下步骤操作：")
                    success_msg.append("1. 关闭当前运行的langbot")
                    success_msg.append("2. 重新启动langbot（服务器用户在控制台输入 docker restart langbot）")
                    success_msg.append("3. 启动完成后即可开始聊天")

                    ctx.add_return("reply", ["\n".join(success_msg)])

                except Exception as e:
                    error_msg = [
                        f"配置更新失败，错误信息：{str(e)}",
                        f"详细错误信息：\n{traceback.format_exc()}"
                    ]
                    if 'provider_backup' in locals() and provider_backup:
                        error_msg.append(f"您可以从备份文件恢复: {os.path.basename(provider_backup)}")
                    ctx.add_return("reply", ["\n".join(error_msg)])

                # 清除用户状态
                del self.user_states[sender_id]
            
            ctx.prevent_default()

    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        if msg.startswith("/一键修改") or msg.startswith("sk-"):
            ctx.add_return("reply", ["为了保护您的API key安全，请私聊机器人进行配置修改。"])
            ctx.prevent_default()

    def __del__(self):
        pass
