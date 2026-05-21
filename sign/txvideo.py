#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import requests.utils
import time
import json
import re

API_URL = "https://v.qq.com"

def extract_cookie_field(cookie, field_name):
    """从 cookie 字符串中提取指定字段的值"""
    match = re.search(rf'{field_name}=([^;]*)', cookie)
    return match.group(1) if match else None

def sign(config):
    cookie = config.get('cookie', '')
    if not cookie:
        return "未配置Cookie"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
        "Referer": "https://v.qq.com/"
    }
    
    results = []
    
    # 验证Cookie - 提取用户名
    try:
        if 'qq_nick=' in cookie:
            nick = cookie.split('qq_nick=')[1].split(';')[0]
            nick = requests.utils.unquote(nick)
            results.append(f"登录成功: {nick}")
        else:
            results.append("登录成功")
    except Exception as e:
        results.append(f"验证失败: {e}")
        return " | ".join(results)
    
    # ========== 第一步：auth_refresh 刷新 session ==========
    millisecond_time = round(time.time() * 1000)
    
    vqq_vuserid = extract_cookie_field(cookie, 'vqq_vuserid')
    vqq_openid = extract_cookie_field(cookie, 'vqq_openid')
    vqq_access_token = extract_cookie_field(cookie, 'vqq_access_token')
    vqq_vusession = extract_cookie_field(cookie, 'vqq_vusession')
    vqq_appid = extract_cookie_field(cookie, 'vqq_appid') or ''
    
    if not all([vqq_vuserid, vqq_openid, vqq_access_token]):
        results.append("Cookie缺少必要字段(vqq_vuserid/vqq_openid/vqq_access_token)")
        return " | ".join(results)
    
    # auth_refresh 获取新的 vqq_vusession
    auth_refresh_url = (
        f"https://access.video.qq.com/user/auth_refresh"
        f"?vappid={vqq_appid}"
        f"&vsecret="
        f"&type=qq"
        f"&g_tk="
        f"&g_vstk="
        f"&g_actk="
        f"&_={millisecond_time}"
    )
    
    refresh_cookie = (
        f"main_login=qq; "
        f"vqq_vuserid={vqq_vuserid}; "
        f"vqq_openid={vqq_openid}; "
        f"vqq_access_token={vqq_access_token}; "
        f"vqq_vusession={vqq_vusession or ''}; "
    )
    
    refresh_headers = {
        'Referer': 'https://v.qq.com',
        'Cookie': refresh_cookie
    }
    
    try:
        login_rsp = requests.get(url=auth_refresh_url, headers=refresh_headers, timeout=10)
        login_rsp_cookie = requests.utils.dict_from_cookiejar(login_rsp.cookies)
        
        if login_rsp.status_code == 200 and login_rsp_cookie:
            new_vusession = login_rsp_cookie.get('vqq_vusession', vqq_vusession or '')
        else:
            new_vusession = vqq_vusession or ''
    except:
        new_vusession = vqq_vusession or ''
    
    # ========== 第二步：签到 ==========
    sign_cookie = (
        f"main_login=qq; "
        f"vqq_appid={vqq_appid}; "
        f"vqq_openid={vqq_openid}; "
        f"vqq_access_token={vqq_access_token}; "
        f"vqq_vuserid={vqq_vuserid}; "
        f"vqq_refresh_token={extract_cookie_field(cookie, 'vqq_refresh_token') or ''}; "
        f"vqq_vusession={new_vusession}; "
    )
    
    sign_headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; U; Android 8.1.0; zh-cn; Mi Note 3 Build/OPM1.171019.019) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.128 '
                      'Mobile Safari/537.36 XiaoMi/MiuiBrowser/10.0.2',
        'Cookie': sign_cookie
    }
    
    try:
        sign_url = "https://vip.video.qq.com/fcgi-bin/comm_cgi?name=hierarchical_task_system&cmd=2"
        r = requests.get(sign_url, headers=sign_headers, timeout=10)
        
        if 'QZOutputJson=' in r.text:
            start_idx = r.text.index('(') + 1
            end_idx = r.text.rindex(')')
            rsp_dict = json.loads(r.text[start_idx:end_idx])
            
            ret = rsp_dict.get('ret')
            
            if ret == 0:
                score = rsp_dict.get('checkin_score', 0)
                results.append(f"签到成功(V力值+{score})")
            elif ret == -10006:
                results.append("签到失败: Cookie已过期")
            elif ret == -110009:
                results.append("签到失败: 需要图形验证，请手动签到一次后更新Cookie")
            else:
                results.append(f"签到失败: {rsp_dict.get('msg', '未知错误')}")
        else:
            # 尝试新接口
            new_url = "https://vip.video.qq.com/rpc/trpc.new_task_system.task_system.TaskSystem/CheckIn?rpc_data=%7B%7D"
            new_headers = {
                'Referer': 'https://film.video.qq.com',
                'Origin': 'https://film.video.qq.com',
                'User-Agent': sign_headers['User-Agent'],
                'Cookie': sign_cookie
            }
            r2 = requests.get(new_url, headers=new_headers, timeout=10)
            rsp_dict = r2.json()
            ret = rsp_dict.get('ret')
            
            if ret == 0:
                score = rsp_dict.get('check_in_score', 0)
                results.append(f"签到成功(V力值+{score})")
            elif ret == -110009:
                results.append("签到失败: 需要图形验证，请手动签到一次后更新Cookie")
            else:
                results.append(f"签到失败(ret={ret})")
    except Exception as e:
        results.append(f"签到请求失败: {str(e)[:30]}")
    
    return " | ".join(results) if results else "签到完成"
