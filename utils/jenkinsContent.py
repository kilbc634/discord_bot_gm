from setting import *
import requests
import base64
import time
from datetime import datetime

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


# 透過定期產生的status.json來檢查，是否長時間(預設60分鐘)都無人在線
def check_player_inactive(inactive_sec = 60 * 60):
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
        status_json = download_status_json(build_number)

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

# 下載並解析 status.json 工件
def download_status_json(build_number):
    artifact_url = f"{Jenkins_job['game_status']}/{build_number}/artifact/status.json"
    response = Jenkins_session.get(artifact_url)
    if response.status_code == 200:
        return response.json()
    return None
