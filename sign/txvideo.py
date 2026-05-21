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
    auth_refresh_url = config.get('auth_refresh_url', '')
    if not cookie:
        return "未配置Cookie"
    
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
        results.append("Cookie缺少必要字段")
        return " | ".join(results)
    
    # 构建 auth_refresh URL
    if auth_refresh_url:
        refresh_url = auth_refresh_url
        if '?' in refresh_url:
            refresh_url += f"&_={millisecond_time}"
        else:
            refresh_url += f"?_={millisecond_time}"
    else:
        refresh_url = (
            f"https://access.video.qq.com/user/auth_refresh"
            f"?vappid={vqq_appid}&vsecret=&type=qq&g_tk=&g_vstk=&g_actk="
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
        login_rsp = requests.get(url=refresh_url, headers=refresh_headers, timeout=10)
        
        if login_rsp.status_code == 401:
            results.append("auth_refresh失败(401)，请配置auth_refresh_url")
            return " | ".join(results)
        
        login_rsp_cookie = requests.utils.dict_from_cookiejar(login_rsp.cookies)
        
        if login_rsp.status_code == 200 and login_rsp_cookie:
            new_vusession = login_rsp_cookie.get('vqq_vusession', vqq_vusession or '')
        else:
            new_vusession = vqq_vusession or ''
    except:
        new_vusession = vqq_vusession or ''
    
    # ========== 第二步：签到（多接口降级） ==========
    sign_cookie = (
        f"main_login=qq; "
        f"vqq_appid={vqq_appid}; "
        f"vqq_openid={vqq_openid}; "
        f"vqq_access_token={vqq_access_token}; "
        f"vqq_vuserid={vqq_vuserid}; "
        f"vqq_refresh_token={extract_cookie_field(cookie, 'vqq_refresh_token') or ''}; "
        f"vqq_vusession={new_vusession}; "
    )
    
    mobile_ua = ('Mozilla/5.0 (Linux; U; Android 8.1.0; zh-cn; Mi Note 3) '
                 'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.128 '
                 'Mobile Safari/537.36')
    
    # 接口列表：先尝试新接口，再尝试旧接口
    apis = [
        ('https://vip.video.qq.com/rpc/trpc.new_task_system.task_system.TaskSystem/CheckIn?rpc_data=%7B%7D',
         {'Referer': 'https://film.video.qq.com', 'Origin': 'https://film.video.qq.com',
          'User-Agent': mobile_ua, 'Cookie': sign_cookie}, 'json'),
        ('https://vip.video.qq.com/fcgi-bin/comm_cgi?name=hierarchical_task_system&cmd=2',
         {'User-Agent': mobile_ua, 'Cookie': sign_cookie}, 'qzoutput'),
    ]
    
    for url, headers, mode in apis:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            rsp_dict = None
            
            if mode == 'qzoutput' and 'QZOutputJson=' in r.text:
                try:
                    s = r.text.index('(') + 1
                    e = r.text.rindex(')')
                    rsp_dict = json.loads(r.text[s:e])
                except:
                    pass
            else:
                try:
                    rsp_dict = r.json()
                except:
                    pass
            
            if rsp_dict:
                ret = rsp_dict.get('ret')
                if ret == 0:
                    score = rsp_dict.get('check_in_score') or rsp_dict.get('checkin_score', 0)
                    results.append(f"签到成功(V力值+{score})")
                    return " | ".join(results)
                elif ret == -10006:
                    results.append("签到失败: Cookie已过期")
                    return " | ".join(results)
                elif ret == -110009:
                    results.append("签到失败: 需要图形验证，请手动签到后更新Cookie")
                    return " | ".join(results)
                elif ret == -10 or 'no match route' in str(rsp_dict.get('msg', '')):
                    continue  # 接口失效，尝试下一个
                else:
                    results.append(f"签到失败(ret={ret})")
                    return " | ".join(results)
        except:
            continue
    
    results.append("签到失败: 所有接口均无效")
    return " | ".join(results)
