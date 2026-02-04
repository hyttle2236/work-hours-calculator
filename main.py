import nest_asyncio  
nest_asyncio.apply()  
import flet as ft  
import datetime  
import os  
from supabase import create_client, Client  
# === 1. 数据库配置 ===  
SUPABASE_URL = os.environ.get("SUPABASE_URL")  
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  
supabase: Client = None  
if SUPABASE_URL and SUPABASE_KEY:  
    try:  
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)  
    except Exception as e:  
        print(f"数据库连接失败: {e}")  
# ==========================================================  
# 2. 数据层  
# ==========================================================  
def load_user_data(user_id):  
    if not supabase or not user_id:  
        return None, "user"  
    try:  
        response = supabase.table('user_records').select("data, role").eq('user_id', str(user_id)).execute()  
        if response.data:  
            record = response.data[0]  
            data = record.get('data') or {"user_info": None, "work_records": []}  
            role = record.get('role') or "user"  
            return data, role  
        return None, "user"  
    except:  
        return None, "user"  
def load_all_users_summary():  
    if not supabase: return []  
    try:  
        response = supabase.table('user_records').select("user_id, data, created_at").order('created_at', desc=True).execute()  
        users = []  
        for row in response.data:  
            uid = row['user_id']  
            data = row.get('data') or {}  
            info = data.get('user_info') or {}  
            users.append({  
                "id": uid,   
                "name": info.get('name', '未命名'),   
                "workshop": info.get('workshop', '-')  
            })  
        return users  
    except:  
        return []  
def save_user_data(user_id, data):  
    if not supabase or not user_id: return  
    try:  
        supabase.table('user_records').update({"data": data}).eq('user_id', str(user_id)).execute()  
    except:  
        try:  
            supabase.table('user_records').upsert({"user_id": str(user_id), "data": data}).execute()  
        except:  
            pass  
def get_beijing_now():  
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)  
# ==========================================================  
# 3. 界面层  
# ==========================================================  
def main(page: ft.Page):  
    page.title = "云端工时本 (最终修复版)"  
    page.theme_mode = "light"  
    page.bgcolor = "white"  
    page.scroll = None  
    page.padding = 0  
    if not supabase:  
        page.add(ft.Container(content=ft.Text("警告：数据库未连接", color="white"), bgcolor="red", padding=10))  
    # === 全局变量 ===  
    logged_in_user_id = None  
    logged_in_role = "user"  
    target_user_id = None  
    target_user_info = {}  
    target_records = []  
      
    editing_index = None  
    temp_date = None  
    active_field = None  
    # === 组件 ===  
    txt_login_name = ft.TextField(label="姓名")  
    # 限制5位工号  
    txt_login_id = ft.TextField(label="工号", keyboard_type="number", max_length=5)  
    txt_login_workshop = ft.TextField(label="车间")  
    txt_login_fleet = ft.TextField(label="车队")  
    txt_train_no = ft.TextField(label="车次", width=150)  
    chk_deadhead = ft.Checkbox(label="便乘")  
    txt_start_time = ft.TextField(label="出勤", read_only=True, width=160, text_size=14)  
    txt_end_time = ft.TextField(label="退勤", read_only=True, width=160, text_size=14)  
      
    txt_total_hours = ft.Text("累计: 0 小时", size=16, weight="bold", color="blue")  
    btn_submit = ft.Button("添加记录", style=ft.ButtonStyle(bgcolor="blue", color="white"))  
    btn_cancel_edit = ft.Button("取消修改", visible=False)  
    data_table = ft.DataTable(  
        bgcolor="white",  
        border=ft.Border.all(1, "#eeeeee"),  
        border_radius=10,  
        columns=[  
            ft.DataColumn(ft.Text("车次")),  
            ft.DataColumn(ft.Text("出勤")),  
            ft.DataColumn(ft.Text("退勤")),  
            ft.DataColumn(ft.Text("工时"), numeric=True),  
            ft.DataColumn(ft.Text("操作")),  
        ],  
        rows=[]  
    )  
    # === 事件逻辑 ===  
    def on_date_change(e):  
        nonlocal temp_date  
        if e.control.value:  
            temp_date = e.control.value + datetime.timedelta(hours=12)  
            date_picker.open = False  
            time_picker.open = True  
            page.update()  
    def on_time_change(e):  
        if e.control.value and temp_date:  
            dt = datetime.datetime.combine(temp_date.date(), e.control.value)  
            val = dt.strftime("%Y-%m-%d %H:%M")  
            if active_field == "start": txt_start_time.value = val  
            else: txt_end_time.value = val  
            page.update()  
    date_picker = ft.DatePicker(on_change=on_date_change)  
    time_picker = ft.TimePicker(on_change=on_time_change)  
    page.overlay.extend([date_picker, time_picker])  
    def open_picker(e, field):  
        nonlocal active_field  
        active_field = field  
        date_picker.value = get_beijing_now()  
        date_picker.open = True  
        page.update()  
    txt_start_time.on_click = lambda e: open_picker(e, "start")  
    txt_end_time.on_click = lambda e: open_picker(e, "end")  
    # === 表格渲染 ===  
    def render_table():  
        data_table.rows.clear()  
        total_h = 0.0  
          
        for i, r in enumerate(target_records):  
            duration = float(r.get('duration', 0))  
            total_h += duration  
              
            # 安全获取时间字符串  
            s_time = r.get('start', '')  
            if ' ' in s_time: s_time = s_time.split(' ')[-1]  
              
            e_time = r.get('end', '')  
            if ' ' in e_time: e_time = e_time.split(' ')[-1]  
            edit_btn = ft.TextButton("修改", on_click=edit_record, data=i)  
            del_btn = ft.TextButton("删除", on_click=del_record, data=i, style=ft.ButtonStyle(color="red"))  
              
            data_table.rows.append(ft.DataRow(cells=[  
                ft.DataCell(ft.Text(r.get('train', ''))),  
                ft.DataCell(ft.Text(s_time)),  
                ft.DataCell(ft.Text(e_time)),  
                ft.DataCell(ft.Text(str(duration))),  
                ft.DataCell(ft.Row([edit_btn, del_btn], spacing=0)),  
            ]))  
          
        txt_total_hours.value = f"累计: {round(total_h, 2)} 小时"  
        page.update()  
    def save_cloud():  
        if target_user_id:  
            save_user_data(target_user_id, {  
                "user_info": target_user_info,  
                "work_records": target_records  
            })  
    def edit_record(e):  
        nonlocal editing_index  
        editing_index = e.control.data  
        r = target_records[editing_index]  
        txt_train_no.value = r.get('train', '')  
        chk_deadhead.value = ("便乘" in r.get('note', ''))  
        txt_start_time.value = f"{r.get('date')} {r.get('start')}"  
        txt_end_time.value = f"{r.get('date')} {r.get('end')}"  
        btn_submit.text = "保存修改"  
        btn_submit.style = ft.ButtonStyle(bgcolor="orange", color="white")  
        btn_cancel_edit.visible = True  
        page.update()  
    def del_record(e):  
        target_records.pop(e.control.data)  
        save_cloud()  
        render_table()  
    def cancel_edit(e):  
        nonlocal editing_index  
        editing_index = None  
        txt_train_no.value = ""  
        chk_deadhead.value = False  
        btn_submit.text = "添加记录"  
        btn_submit.style = ft.ButtonStyle(bgcolor="blue", color="white")  
        btn_cancel_edit.visible = False  
        page.update()  
    def submit_record(e):  
        try:  
            if not txt_start_time.value or not txt_end_time.value:   
                page.snack_bar = ft.SnackBar(ft.Text("请选择时间"))  
                page.snack_bar.open = True  
                page.update()  
                return  
            fmt = "%Y-%m-%d %H:%M"  
            s = datetime.datetime.strptime(txt_start_time.value, fmt)  
            e = datetime.datetime.strptime(txt_end_time.value, fmt)  
              
            if e <= s:  
                page.snack_bar = ft.SnackBar(ft.Text("退勤必须晚于出勤"))  
                page.snack_bar.open = True  
                page.update()  
                return  
            duration = (e - s).total_seconds() / 3600  
            extra = 0.5 if (not txt_train_no.value.upper().startswith("C") and not chk_deadhead.value) else 0.0  
              
            record = {  
                "date": s.strftime("%Y-%m-%d"),  
                "train": txt_train_no.value.upper() or "无车次",  
                "start": s.strftime("%H:%M"),  
                "end": e.strftime("%H:%M"),  
                "duration": round(duration + extra, 2),  
                "note": "自动计算"  
            }  
            nonlocal editing_index  
            if editing_index is not None:  
                target_records[editing_index] = record  
                cancel_edit(None)  
            else:  
                target_records.insert(0, record)  
                txt_train_no.value = ""  
                chk_deadhead.value = False  
              
            save_cloud()  
            render_table()  
        except:  
            page.snack_bar = ft.SnackBar(ft.Text("时间格式错误"))  
            page.snack_bar.open = True  
            page.update()  
    btn_submit.on_click = submit_record  
    btn_cancel_edit.on_click = cancel_edit  
    # === 页面逻辑 ===  
    def handle_login(e):  
        nonlocal logged_in_user_id, logged_in_role  
        nonlocal target_user_id, target_user_info, target_records  
        uid = txt_login_id.value.strip()  
        if not uid: return  
        page.splash = ft.ProgressBar()  
        page.update()  
        data, role = load_user_data(uid)  
        logged_in_user_id = uid  
        logged_in_role = role  
        if data:  
            target_user_info = data.get('user_info', {})  
            target_records = data.get('work_records', [])  
            txt_login_name.value = target_user_info.get('name', '')  
            txt_login_workshop.value = target_user_info.get('workshop', '')  
            txt_login_fleet.value = target_user_info.get('fleet', '')  
        else:  
            target_user_info = {  
                "name": txt_login_name.value, "id": uid,  
                "workshop": txt_login_workshop.value, "fleet": txt_login_fleet.value  
            }  
            target_records = []  
            save_user_data(uid, {"user_info": target_user_info, "work_records": target_records})  
          
        target_user_id = logged_in_user_id  
        page.splash = None  
          
        if logged_in_role == 'admin':  
            show_admin_dashboard()  
        else:  
            show_work_page(is_admin_viewing=False)  
    def handle_admin_click_user(e):  
        selected_uid = e.control.data  
        nonlocal target_user_id, target_user_info, target_records  
        page.splash = ft.ProgressBar()  
        page.update()  
          
        target_user_id = selected_uid  
        data, _ = load_user_data(target_user_id)  
        if data:  
            target_user_info = data.get('user_info', {})  
            target_records = data.get('work_records', [])  
            show_work_page(is_admin_viewing=True)  
        page.splash = None  
    def show_admin_dashboard():  
        page.clean()  
        users = load_all_users_summary()  
        lv = ft.ListView(expand=True, spacing=10)  
        for u in users:  
            uid = u['id']  
            name = u['name']  
            workshop = u['workshop']  
            card = ft.Card(content=ft.Container(    
    content=ft.ListTile(    
        leading=ft.Icon(ft.icons.PERSON),    
        title=ft.Text(f"{name} ({uid})"),    
        subtitle=ft.Text(f"{workshop}"),    
        trailing=ft.Icon(ft.icons.ARROW_FORWARD_IOS, size=14),    
        on_click=handle_admin_click_user,    
        data=uid    
    ),    
    padding=10    
))    
            lv.controls.append(card)  
        page.add(ft.Column([  
            ft.Container(  
                content=ft.Row([  
                    ft.Text("超级管理员后台", size=20, weight="bold", color="white"),  
                    ft.IconButton(ft.icons.LOGOUT, icon_color="white", on_click=lambda e: show_login_page())  
                ], alignment="spaceBetween"),  
                bgcolor="red", padding=15  
            ),  
            ft.Container(content=lv, padding=10, expand=True)  
        ], expand=True))  
    def show_work_page(is_admin_viewing=False):  
        page.clean()  
        if is_admin_viewing:  
            header = ft.Container(  
                content=ft.Row([  
                    ft.IconButton(ft.icons.ARROW_BACK, icon_color="white", on_click=lambda e: show_admin_dashboard()),  
                    ft.Text(f"正在管理: {target_user_info.get('name')}", color="white", weight="bold"),  
                    ft.Icon(ft.icons.ADMIN_PANEL_SETTINGS, color="white")  
                ], alignment="spaceBetween"),  
                bgcolor="orange", padding=10  
            )  
        else:  
            header = ft.Container(  
                content=ft.Row([  
                    ft.Column([  
                        ft.Text(f"欢迎, {target_user_info.get('name')}", weight="bold"),  
                        ft.Text(f"工号: {target_user_id}", size=12, color="grey"),  
                    ]),  
                    ft.TextButton("退出", on_click=lambda e: show_login_page())  
                ], alignment="spaceBetween"),  
                padding=10  
            )  
        # 布局容器  
        page.add(ft.Column([  
            header,  
            ft.Divider(height=1),  
            ft.Container(  
                padding=10,  
                content=ft.Column([  
                    ft.Text("录入/修改工时", weight="bold"),  
                    ft.Row([txt_train_no, chk_deadhead]),  
                    ft.Row([txt_start_time, txt_end_time]),  
                    ft.Row([btn_submit, btn_cancel_edit]),  
                    ft.Divider(),  
                    ft.Row([  
                        ft.Text("记录列表", weight="bold"),  
                        txt_total_hours  
                    ], alignment="spaceBetween"),  
                    ft.Container(  
                        content=ft.Row([data_table], scroll="auto"),  
                        border=ft.Border.all(1, "#eeeeee"),  
                        border_radius=10,  
                    )  
                ], scroll="auto", expand=True)  
            )  
        ], expand=True))  
        render_table()  
    def show_login_page():  
        page.clean()  
        nonlocal logged_in_user_id  
        logged_in_user_id = None  
        page.add(ft.Column([  
            ft.Container(height=50),  
            ft.Icon(ft.icons.SCHEDULE, size=60, color="blue"),  
            ft.Text("云端工时本", size=24, weight="bold"),  
            ft.Text("企业版 v1.0", size=14, color="grey"),  
            ft.Container(height=30),  
            ft.Container(txt_login_name, width=280),  
            ft.Container(txt_login_id, width=280),  
            ft.Container(txt_login_workshop, width=280),  
            ft.Container(txt_login_fleet, width=280),  
            ft.Container(height=20),  
            ft.Button("进入系统", on_click=handle_login, width=200, height=45),  
        ], horizontal_alignment="center", alignment="center", scroll="auto"))  
    show_login_page()  
if __name__ == "__main__":  
    port = int(os.environ.get("PORT", 8080))  
    ft.run(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")  
