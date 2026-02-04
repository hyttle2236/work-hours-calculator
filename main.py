import nest_asyncio
nest_asyncio.apply()

import flet as ft
import datetime
import csv
import io
import urllib.parse
import json
import os
from supabase import create_client, Client

# === 云数据库配置 ===
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"连接数据库失败: {e}")

# ==========================================================

def load_data_by_id(user_id):
    if not supabase or not user_id:
        return {"user_info": None, "work_records": []}
    
    try:
        response = supabase.table('user_records').select("data").eq('user_id', str(user_id)).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]['data']
        else:
            return {"user_info": None, "work_records": []}
    except Exception as e:
        print(f"读取数据失败: {e}")
        return {"user_info": None, "work_records": []}

def save_data_by_id(user_id, data):
    if not supabase or not user_id:
        return
    
    try:
        payload = {"user_id": str(user_id), "data": data}
        supabase.table('user_records').upsert(payload).execute()
    except Exception as e:
        print(f"保存数据失败: {e}")

# ==========================================================

def get_beijing_now():
    utc_now = datetime.datetime.utcnow()
    beijing_time = utc_now + datetime.timedelta(hours=8)
    return beijing_time

def main(page: ft.Page):
    page.title = "云端工时本 (多用户版)"
    page.theme_mode = "light"
    page.bgcolor = "white"
    # 关闭页面级滚动，防止和表格滚动冲突导致布局错误
    page.scroll = None 
    page.window_width = 600
    page.window_height = 800
    page.padding = 0 # 设为0，让滚动条贴边

    # 检查数据库
    if not supabase:
        page.add(ft.Container(
            content=ft.Text("警告：数据库未连接，请检查环境变量配置！", color="white"),
            bgcolor="red", padding=10
        ))

    # === 全局状态 ===
    current_user_id = None
    current_user_info = None
    current_records = []
    
    editing_index = None
    temp_date = None
    active_field = None

    # === 组件 ===
    txt_name = ft.TextField(label="姓名")
    txt_id = ft.TextField(label="工号 (必填，唯一账号)", keyboard_type="number")
    txt_workshop = ft.TextField(label="车间")
    txt_fleet = ft.TextField(label="车队")

    txt_train_no = ft.TextField(label="车次", width=150)
    chk_deadhead = ft.Checkbox(label="便乘", value=False)
    
    txt_start_time = ft.TextField(label="出勤 (北京时间)", width=280, read_only=True, icon="access_time")
    txt_end_time = ft.TextField(label="退勤 (北京时间)", width=280, read_only=True, icon="access_time")
    
    try:
        Btn = ft.FilledButton
    except:
        Btn = ft.ElevatedButton

    btn_submit = Btn("添加记录", style=ft.ButtonStyle(bgcolor="blue", color="white"))
    btn_cancel_edit = Btn("取消", style=ft.ButtonStyle(bgcolor="grey", color="white"), visible=False)

    # === 时间选择器逻辑 ===
    def handle_date_change(e):
        nonlocal temp_date
        if e.control.value:
            temp_date = e.control.value + datetime.timedelta(hours=12)
            date_picker.open = False
            time_picker.open = True
            page.update()

    def handle_time_change(e):
        if e.control.value and temp_date:
            final_dt = datetime.datetime.combine(temp_date.date(), e.control.value)
            formatted = final_dt.strftime("%Y-%m-%d %H:%M")
            if active_field == "start":
                txt_start_time.value = formatted
            elif active_field == "end":
                txt_end_time.value = formatted
            time_picker.open = False
            page.update()

    date_picker = ft.DatePicker(on_change=handle_date_change)
    time_picker = ft.TimePicker(on_change=handle_time_change)
    page.overlay.append(date_picker)
    page.overlay.append(time_picker)

    def trigger_picker(e, field_type):
        nonlocal active_field
        active_field = field_type
        date_picker.value = get_beijing_now()
        date_picker.open = True
        page.update()

    txt_start_time.on_click = lambda e: trigger_picker(e, "start")
    txt_end_time.on_click = lambda e: trigger_picker(e, "end")

    # === 表格 ===
    data_table = ft.DataTable(
        # 【关键修改】移除无限宽度，防止 Web 端布局崩溃
        # width=float("inf"), 
        
        bgcolor="white",
        border=ft.border.all(1, "#eeeeee"),
        border_radius=10,
        vertical_lines=ft.border.BorderSide(1, "#eeeeee"),
        horizontal_lines=ft.border.BorderSide(1, "#eeeeee"),
        heading_row_color="#E3F2FD",
        columns=[
            ft.DataColumn(ft.Text("车次", weight="bold")),
            ft.DataColumn(ft.Text("出勤", weight="bold")),
            ft.DataColumn(ft.Text("退勤", weight="bold")),
            ft.DataColumn(ft.Text("工时", weight="bold"), numeric=True),
            ft.DataColumn(ft.Text("操作", weight="bold")),
        ],
        rows=[]
    )

    # === 核心逻辑 ===

    def login_action(e):
        if not txt_id.value:
            page.snack_bar = ft.SnackBar(ft.Text("必须填写工号，这是你的唯一账号"))
            page.snack_bar.open = True
            page.update()
            return

        nonlocal current_user_id, current_user_info, current_records
        current_user_id = txt_id.value.strip()

        page.splash = ft.ProgressBar()
        page.update()

        cloud_data = load_data_by_id(current_user_id)
        
        if cloud_data and cloud_data.get("user_info"):
            saved_info = cloud_data.get("user_info")
            current_user_info = saved_info
            current_records = cloud_data.get("work_records", [])
            txt_name.value = saved_info.get("name", "")
            txt_workshop.value = saved_info.get("workshop", "")
            txt_fleet.value = saved_info.get("fleet", "")
        else:
            current_user_info = {
                "name": txt_name.value,
                "id": txt_id.value,
                "workshop": txt_workshop.value,
                "fleet": txt_fleet.value
            }
            current_records = []
            sync_to_cloud()

        page.splash = None
        show_main_interface()

    def sync_to_cloud():
        if current_user_id:
            full_data = {
                "user_info": current_user_info,
                "work_records": current_records
            }
            save_data_by_id(current_user_id, full_data)

    def load_record_for_edit(e):
        nonlocal editing_index
        index = e.control.data
        record = current_records[index]
        txt_train_no.value = record['train'] if record['train'] != "无车次" else ""
        chk_deadhead.value = True if "便乘" in record['note'] else False
        txt_start_time.value = f"{record['date']} {record['start']}"
        txt_end_time.value = f"{record['date']} {record['end']}"
        editing_index = index
        btn_submit.text = "保存修改"
        btn_submit.style = ft.ButtonStyle(bgcolor="orange", color="white")
        btn_cancel_edit.visible = True
        page.update()

    def cancel_edit_action(e):
        nonlocal editing_index
        editing_index = None
        txt_train_no.value = ""
        chk_deadhead.value = False
        btn_submit.text = "添加记录"
        btn_submit.style = ft.ButtonStyle(bgcolor="blue", color="white")
        btn_cancel_edit.visible = False
        page.update()

    def delete_record_action(e):
        nonlocal editing_index
        index = e.control.data
        if editing_index == index:
            cancel_edit_action(None)
        elif editing_index is not None and index < editing_index:
            editing_index -= 1
        current_records.pop(index)
        sync_to_cloud()
        update_table()

    def calculate_hours(e):
        try:
            train = txt_train_no.value.strip().upper()
            is_dh = chk_deadhead.value
            fmt = "%Y-%m-%d %H:%M"
            if not txt_start_time.value or not txt_end_time.value:
                page.snack_bar = ft.SnackBar(ft.Text("请先选择时间"))
                page.snack_bar.open = True
                page.update()
                return

            start = datetime.datetime.strptime(txt_start_time.value, fmt)
            end = datetime.datetime.strptime(txt_end_time.value, fmt)
            if end <= start:
                page.snack_bar = ft.SnackBar(ft.Text("退勤时间必须晚于出勤"))
                page.snack_bar.open = True
                page.update()
                return

            duration = (end - start).total_seconds() / 3600
            extra = 0.5 if (not train.startswith("C") and not is_dh) else 0.0
            note = "标准作业" if extra > 0 else "便乘/C字头"
            
            record = {
                "date": start.strftime("%Y-%m-%d"),
                "train": train if train else "无车次",
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "duration": round(duration + extra, 2),
                "note": note
            }
            
            nonlocal editing_index
            if editing_index is not None:
                current_records[editing_index] = record
                cancel_edit_action(None)
            else:
                current_records.insert(0, record)
                txt_train_no.value = ""
                chk_deadhead.value = False
            
            sync_to_cloud()
            update_table()
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("日期格式错误"))
            page.snack_bar.open = True
            page.update()

    def update_table():
        data_table.rows.clear()
        for i, r in enumerate(current_records):
            try:
                dt_start_full = datetime.datetime.strptime(f"{r['date']} {r['start']}", "%Y-%m-%d %H:%M")
                start_str = dt_start_full.strftime("%m-%d %H:%M")
                
                # 【修复核心】这里不再使用 IconButton，全部改用 TextButton (纯文字按钮)
                # 这样可以 100% 避免图标加载失败导致的 "must have icon" 报错
                data_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(r['train'])),
                            ft.DataCell(ft.Text(start_str)),
                            ft.DataCell(ft.Text(r['end'])),
                            ft.DataCell(ft.Text(str(r['duration']), weight="bold", color="blue")),
                            ft.DataCell(
                                ft.Row([
                                    ft.TextButton(
                                        "修改",
                                        on_click=load_record_for_edit,
                                        data=i
                                    ),
                                    ft.TextButton(
                                        "删除",
                                        on_click=delete_record_action,
                                        data=i,
                                        style=ft.ButtonStyle(color="red")
                                    ),
                                ], spacing=0)
                            ),
                        ]
                    )
                )
            except Exception as ex:
                print(f"更新表格行出错: {ex}")
        page.update()

    def show_main_interface():
        page.clean()
        
        # 页面布局容器
        main_content = ft.Column(
            controls=[
                ft.Row([
                    ft.Column([
                        ft.Text(f"欢迎 {current_user_info.get('name', '用户')}", size=18, weight="bold"),
                        ft.Text(f"工号: {current_user_id}", size=12, color="grey"),
                    ]),
                    ft.TextButton("退出登录", on_click=lambda e: show_login_interface())
                ], alignment="spaceBetween"),
                
                ft.Divider(),
                ft.Text("录入工时", weight="bold"),
                ft.Row([txt_train_no, chk_deadhead]),
                txt_start_time,
                txt_end_time,
                ft.Row([btn_submit, btn_cancel_edit]),

                ft.Divider(),
                ft.Text("历史记录", weight="bold"),
                
                # 使用 Row 和 Container 包裹表格，实现横向滚动，防止手机屏幕不够宽
                ft.Container(
                    content=ft.Row([data_table], scroll="auto"),
                    border=ft.border.all(1, "#eeeeee"),
                    border_radius=10,
                ),
            ],
            scroll="auto", # 内容垂直滚动
            expand=True
        )

        page.add(main_content)
        btn_submit.on_click = calculate_hours
        btn_cancel_edit.on_click = cancel_edit_action
        update_table()

    def show_login_interface():
        page.clean()
        # 重置当前用户状态
        nonlocal current_user_id
        current_user_id = None
        
        page.add(
            ft.Column([
                ft.Text("云端工时本", size=32, weight="bold", text_align="center"),
                ft.Text("多用户版", size=14, color="grey", text_align="center"),
                ft.Divider(),
                ft.Text("登录 / 注册", size=18, weight="bold"),
                txt_name,
                txt_id,
                txt_workshop,
                txt_fleet,
                ft.ElevatedButton(
                    "登录",
                    on_click=login_action,
                    width=200,
                    height=50,
                    style=ft.ButtonStyle(bgcolor="blue", color="white")
                ),
            ], horizontal_alignment="center", spacing=20, alignment="center")
        )

    show_login_interface()

if __name__ == "__main__":
    # 【部署修复】从环境变量获取端口，否则 Zeabur 可能无法访问
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 服务正在启动，监听端口: {port}")
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")
