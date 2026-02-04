import flet as ft
import datetime
import csv
import io
import urllib.parse
import json
import os

# === 数据存储工具 ===
DATA_FILE = "app_data.json"

# === 核心工具：强制获取北京时间 (UTC+8) ===
def get_beijing_now():
    # 获取 UTC 时间，然后强制加上 8 小时时差
    utc_now = datetime.datetime.utcnow()
    beijing_time = utc_now + datetime.timedelta(hours=8)
    return beijing_time

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"user_info": None, "work_records": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"user_info": None, "work_records": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================================

def main(page: ft.Page):
    page.title = "工时计算器 (北京时间版)"
    page.theme_mode = "light"
    page.bgcolor = "white"
    page.scroll = "auto"
    page.window_width = 600
    page.window_height = 800
    page.padding = 20

    # === 全局数据 ===
    local_data = load_data()
    current_user = local_data.get("user_info")
    current_records = local_data.get("work_records", [])
    editing_index = None 
    
    temp_date = None
    active_field = None

    # === 组件声明 ===
    txt_name = ft.TextField(label="姓名")
    txt_id = ft.TextField(label="工号", keyboard_type="number")
    txt_workshop = ft.TextField(label="车间")
    txt_fleet = ft.TextField(label="车队")

    txt_train_no = ft.TextField(label="车次", width=150)
    chk_deadhead = ft.Checkbox(label="便乘", value=False)
    
    txt_start_time = ft.TextField(label="出勤时间 (北京时间)", width=280, read_only=True, icon="access_time")
    txt_end_time = ft.TextField(label="退勤时间 (北京时间)", width=280, read_only=True, icon="access_time")
    
    # 兼容按钮
    try:
        Btn = ft.FilledButton
    except:
        Btn = ft.ElevatedButton

    btn_submit = Btn("添加记录", style=ft.ButtonStyle(bgcolor="blue", color="white"))
    btn_cancel_edit = Btn("取消", style=ft.ButtonStyle(bgcolor="grey", color="white"), visible=False)

    # === 日期/时间选择逻辑 (核心修正) ===
    
    def handle_date_change(e):
        nonlocal temp_date
        if e.control.value:
            raw_date = e.control.value
            # 【关键修正】
            # DatePicker 返回的是 00:00:00。
            # 为了防止时区转换导致日期倒退（变回前一天），我们人为加上 12 小时。
            # 这样日期就变成了当天的中午 12:00，无论时区怎么偏，都在当天。
            safe_date = raw_date + datetime.timedelta(hours=12)
            temp_date = safe_date
            
            # 关闭日期，开启时间
            date_picker.open = False
            time_picker.open = True
            page.update()

    def handle_time_change(e):
        if e.control.value and temp_date:
            time_obj = e.control.value
            # 组合日期和时间
            final_dt = datetime.datetime.combine(temp_date.date(), time_obj)
            
            # 强制格式化为 24小时制
            formatted = final_dt.strftime("%Y-%m-%d %H:%M")
            
            if active_field == "start":
                txt_start_time.value = formatted
            elif active_field == "end":
                txt_end_time.value = formatted
            
            time_picker.open = False
            page.update()

    # 初始化选择器
    date_picker = ft.DatePicker(on_change=handle_date_change)
    time_picker = ft.TimePicker(on_change=handle_time_change)

    page.overlay.append(date_picker)
    page.overlay.append(time_picker)

    def trigger_picker(e, field_type):
        nonlocal active_field
        active_field = field_type
        
        # 每次打开选择器时，重置为当前的北京时间
        bj_now = get_beijing_now()
        date_picker.value = bj_now
        
        date_picker.open = True
        page.update()

    txt_start_time.on_click = lambda e: trigger_picker(e, "start")
    txt_end_time.on_click = lambda e: trigger_picker(e, "end")

    # === 表格组件 ===
    
    data_table = ft.DataTable(
        width=float("inf"),
        bgcolor="white",
        border=ft.Border.all(1, "#eeeeee"), 
        border_radius=10,
        vertical_lines=ft.border.BorderSide(1, "#eeeeee"),
        horizontal_lines=ft.border.BorderSide(1, "#eeeeee"),
        heading_row_color="#E3F2FD", 
        columns=[
            ft.DataColumn(ft.Text("车次", weight="bold")),
            ft.DataColumn(ft.Text("出勤", weight="bold")),
            ft.DataColumn(ft.Text("退勤", weight="bold")),
            ft.DataColumn(ft.Text("劳时", weight="bold"), numeric=True),
            ft.DataColumn(ft.Text("操作", weight="bold")),
        ],
        rows=[]
    )

    # === 业务逻辑函数 ===

    def save_user_info_action(e):
        if not all([txt_name.value, txt_id.value, txt_workshop.value, txt_fleet.value]):
            page.snack_bar = ft.SnackBar(ft.Text("请填写完整信息"))
            page.snack_bar.open = True
            page.update()
            return

        info = {
            "name": txt_name.value,
            "id": txt_id.value,
            "workshop": txt_workshop.value,
            "fleet": txt_fleet.value
        }
        nonlocal current_user
        current_user = info
        local_data["user_info"] = info
        save_data(local_data)
        show_main_interface()

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
        
        page.scroll_to(0, duration=500)
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
        local_data["work_records"] = current_records
        save_data(local_data)
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
            
            save_data(local_data)
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
            except:
                start_str = f"{r['date'][5:]} {r['start']}"

            data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(r['train'])),
                        ft.DataCell(ft.Text(start_str, size=12)),
                        ft.DataCell(ft.Text(r['end'], size=12)),
                        ft.DataCell(ft.Text(str(r['duration']), weight="bold", color="blue")),
                        ft.DataCell(
                            ft.Row([
                                ft.TextButton("修改", icon="edit", style=ft.ButtonStyle(color="blue"), data=i, on_click=load_record_for_edit),
                                ft.TextButton("删除", icon="delete", style=ft.ButtonStyle(color="red"), data=i, on_click=delete_record_action)
                            ], spacing=0)
                        ),
                    ]
                )
            )
        
        total_h = sum([r['duration'] for r in current_records])
        txt_total_hours.value = f"累计工时: {total_h} 小时"
        page.update()

    txt_total_hours = ft.Text("累计工时: 0 小时", size=18, weight="bold", color="blue")

    def export_data(e):
        if not current_records: return
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["日期", "车次", "开始", "结束", "工时", "备注"])
        for r in current_records:
            writer.writerow([r['date'], r['train'], r['start'], r['end'], r['duration'], r['note']])
        encoded = urllib.parse.quote(output.getvalue())
        page.launch_url(f"data:text/csv;charset=utf-8,\ufeff{encoded}")

    def clear_data(e):
        current_records.clear()
        save_data(local_data)
        update_table()

    def logout(e):
        local_data["user_info"] = None
        save_data(local_data)
        nonlocal current_user
        current_user = None
        show_login_interface()

    # === 界面切换 ===

    def show_login_interface():
        page.clean()
        page.add(
            ft.Column([
                ft.Text("工时计算器 (北京时间版)", size=30, weight="bold", color="black"),
                ft.Text("首次使用请登记信息", color="grey"),
                txt_name, txt_id, txt_workshop, txt_fleet,
                Btn("进入系统", on_click=save_user_info_action, width=200)
            ], alignment="center", horizontal_alignment="center")
        )

    def show_main_interface():
        page.clean()
        
        # 初始化时，使用北京时间
        bj_now = get_beijing_now()
        
        if not txt_start_time.value:
            txt_start_time.value = bj_now.strftime("%Y-%m-%d %H:%M")
        if not txt_end_time.value:
            txt_end_time.value = (bj_now + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        
        btn_submit.on_click = calculate_hours
        btn_cancel_edit.on_click = cancel_edit_action
        
        page.add(
            ft.Column([
                ft.Row([
                    ft.Text(f"用户: {current_user['name']}", size=16, weight="bold"),
                    ft.TextButton("退出", icon="logout", on_click=logout)
                ], alignment="spaceBetween"),
                
                ft.Divider(),
                
                ft.Text("录入工时", weight="bold", size=16),
                ft.Row([txt_train_no, chk_deadhead]),
                txt_start_time,
                txt_end_time,
                ft.Row([btn_submit, btn_cancel_edit]),
                
                ft.Divider(),
                
                ft.Row([
                    txt_total_hours,
                    ft.Row([
                        ft.OutlinedButton("清空", icon="delete_forever", on_click=clear_data),
                        ft.OutlinedButton("导出", icon="download", on_click=export_data)
                    ])
                ], alignment="spaceBetween"),
                
                ft.Container(
                    content=ft.Column([data_table], scroll="auto"), 
                    border=ft.Border.all(1, "#eeeeee"),
                    border_radius=10,
                )
            ])
        )
        update_table()

    if current_user:
        show_main_interface()
    else:
        show_login_interface()
    # 【修复核心 1】获取 Zeabur 分配的端口，如果没有则默认 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 服务正在启动，监听端口: {port}")
    # 【修复核心 2】
    # view=ft.AppView.WEB_BROWSER : 强制 Web 模式
    # host="0.0.0.0" : 允许外部访问 (解决 502 的关键)
    # port=port : 使用正确端口
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")