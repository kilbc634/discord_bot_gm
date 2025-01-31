from setting import *
import requests
import base64
import time
from datetime import datetime, timedelta
import json
import re

# 設置Jnekins job，有可能會用到的job url都在這裡
Jenkins_job = {
    'game_status': f'{JENKINS_HOST}/job/game_{GAME_SERVER_CODE}_status',
    'game_start': f'{JENKINS_HOST}/job/game_{GAME_SERVER_CODE}_start',
    'game_stop': f'{JENKINS_HOST}/job/game_{GAME_SERVER_CODE}_stop',
}

# 初始化Jnekins REST API的請求session
auth_str = f'{JENKINS_USER}:{JENKINS_TOKEN}'
auth_bytes = auth_str.encode('utf-8')
auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

Jenkins_session = requests.Session()
Jenkins_session.headers.update({
    'Authorization': f'Basic {auth_base64}'
})


#############################################################################
#
#    函式區塊
#
#############################################################################
def post_job_status():
    response = Jenkins_session.post(f"{Jenkins_job['game_status']}/build")
    if response.status_code == 201:
        print("已排程，將更新伺服器狀態")
    else:
        print(f"Failed to trigger build. Status code: {response.status_code}")

def post_job_start():
    response = Jenkins_session.post(f"{Jenkins_job['game_start']}/build")
    if response.status_code == 201:
        print("已排程，將啟動伺服器")
    else:
        print(f"Failed to trigger build. Status code: {response.status_code}")

def post_job_stop():
    response = Jenkins_session.post(f"{Jenkins_job['game_stop']}/build")
    if response.status_code == 201:
        print("已排程，將停止伺服器")
    else:
        print(f"Failed to trigger build. Status code: {response.status_code}")


# 透過jenkins產生的status.json來檢查，是否長時間(預設60分鐘)都無人在線
def check_player_inactive(inactive_sec = 60 * 60):
    # 滿意工廠: jenkins定時執行status檢查，每次檢查只能帶出「當前在線人數」
    # 需要從最新的構建依序往回推算。連續多次檢查都是無人在線，並且檢查時間已超出inactive_sec則判斷為True
    if GAME_SERVER_CODE == 'satisfactory-server':
        # 從最新的構建開始往回檢查
        build_number = get_last_build_number()
        print(f"最新的建構是 build_number = {build_number}")

        while build_number > 0:
            print(f"開始檢查建構 build_number = {build_number}")
            # 獲取該構建的信息
            build_info = get_build_info(build_number)

            # 獲取構建的狀態和開始時間
            if not build_info or build_info['result'] != 'SUCCESS':
                print("檢測到建構沒有成功")
                return False

            # 下載並解析 status.json 工件
            status_file = download_status_file(build_number, 'status.json')
            status_json = json.loads(status_file)

            if status_json:
                num_connected_players = status_json['data']['serverGameState']['numConnectedPlayers']

                # 如果有玩家在線，返回 False
                if num_connected_players != 0:
                    print("檢測到有在線玩家")
                    return False
            else:
                # 如果無法獲取 status.json，則認為構建無效
                print("無法獲取status.json")
                return False

            # 獲取構建的開始時間，並計算距離當前時間的差值
            build_start_time = build_info['timestamp'] / 1000  # Jenkins 返回的是毫秒
            current_time = time.time()
            time_difference = current_time - build_start_time

            # 如果構建的開始時間超過一小時，則結束
            if time_difference > inactive_sec:
                print(f"已確認長時間無玩家在線!!! build_start_time = {build_start_time} & current_time = {current_time}")
                return True
            else:
                print(f"建構時間尚未超時 build_start_time = {build_start_time}")

            # 構建結束且無玩家在線，繼續檢查上一個構建
            build_number = build_number - 1

        # 沒有找到符合條件的構建，返回 False
        print("已經檢查了所有建構")
        return False

    # 幻獸帕魯: 主動執行jenkins的status檢查，將帶出當次啟用至今「玩家登入登出紀錄(含有時間戳)」
    # 透過解析所有登入登出紀錄，可以推算出來當前在線玩家。如果無人在線，且最後一筆登出紀錄時間超出inactive_sec則判斷為True
    if GAME_SERVER_CODE == 'palworld-dedicated-server':
        # 執行status檢查job
        post_job_status()
        time.sleep(10)

        build_number = get_last_build_number()
        print(f"最新的建構是 build_number = {build_number}")

        # 輪巡等待job執行完成
        start_time = time.time()
        timeout_sec = 60
        for times in range(100):
            print("第 {times} 次確認job執行狀態....".format(times=str(times)))
            # 獲取該構建的信息
            build_info = get_build_info(build_number)
            if not build_info.get('building', True):
                print(f"執行完成，其結果是: {build_info.get('result')}")
                break
            if time.time() - start_time > timeout_sec:
                print("輪巡等待job已超時")
                return False
            time.sleep(5)

        # 嘗試獲取status.log
        build_info_stable = get_build_info(build_number)
        if build_info_stable['result'] != 'SUCCESS':
            print("檢測到建構沒有成功")
            return False
        status_file = download_status_file(build_number, 'status.log')

        if status_file:
            # 解析status.log的登入登出訊息
            log_entries = []
    
            # 正則表達式匹配 登入/登出 訊息
            # sample:
            # palworld-server | [2025-01-16 13:49:35] [LOG] Tsukumo0114 joined the server. (User id: steam_76561198131832310)
            # palworld-server | [2025-01-16 13:51:36] [LOG] Tsukumo0114 left the server. (User id: steam_76561198131832310)
            pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[LOG\] (.+?) (joined|left) the server\. \(User id: (steam_\d+)\)")

            for match in pattern.finditer(status_file):
                timestamp, username, action, steam_id = match.groups()
                log_entries.append({
                    'actionType': action, # joined | left
                    'userName': username, # Tsukumo0114
                    'userId': steam_id, # steam_76561198131832310
                    'timestamp': timestamp # 2025-01-16 13:51:36
                })

            # 推算出當前在線玩家
            online_user = {}
            for log in log_entries:
                if log['actionType'] == 'joined':
                    online_user[log['userId']] = {
                        'userName': log['userName'],
                        'userId': log['userId'],
                        'timestamp': log['timestamp']
                    }
                elif log['actionType'] == 'left':
                    del online_user[log['userId']]

            if len(online_user) >= 1:
                online_text = ''
                for userId in online_user.keys():
                    online_text = online_text + f"{userId} - {online_user[userId]['userName']}" + '\n'
                print("當前在線玩家:")
                print(online_text)
                return False
            else:
                print("當前無玩家在線")

            # 如果無人在線，檢查最後一筆登出紀錄時間
            last_log = log_entries[-1]
            log_time = datetime.strptime(last_log['timestamp'], "%Y-%m-%d %H:%M:%S")
            now_time = datetime.now()
            time_difference = now_time - log_time
            if time_difference > timedelta(seconds=inactive_sec):
                # 最後一筆登出紀錄已超時
                print(f"已確認長時間無玩家在線!!! log_time = {log_time} & now_time = {now_time}")
                return True
            else:
                # 最後一筆登出紀錄尚未超時
                print("最後一筆登出紀錄尚未超時")
                return False
                

        else:
            # 如果無法獲取 status.log，則認為構建無效
            print("無法獲取status.log")
            return False


# 獲取最新構建的編號
def get_last_build_number():
    last_build_info_url = f"{Jenkins_job['game_status']}/lastBuild/api/json"
    response = Jenkins_session.get(last_build_info_url)
    if response.status_code == 200:
        return response.json()['number']
    return None

# 獲取特定構建的詳細信息
def get_build_info(build_number):
    build_info_url = f"{Jenkins_job['game_status']}/{build_number}/api/json"
    response = Jenkins_session.get(build_info_url)
    if response.status_code == 200:
        return response.json()
    return None

# 下載並解析 status 工件
def download_status_file(build_number, file_name):
    artifact_url = f"{Jenkins_job['game_status']}/{build_number}/artifact/{file_name}"
    response = Jenkins_session.get(artifact_url)
    if response.status_code == 200:
        return response.text
    return None
