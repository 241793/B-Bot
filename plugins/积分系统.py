__version__ = '0.0.1'
__author__ = 'bucai'
__description__ = '积分、库存系统，可以上架一些卡密，通过签到获取积分兑换。指令：积分签到、积分查询、积分库存，管理员指令：积分库存、积分授权。如何接入本系统，bot_point_config为配置桶，bot_point为用户数据桶'

__param__ = {"required" :False ,"key" :"bot_point_config.range" ,"bool" :False ,"placeholder" :"签到积分范围","name" :"签到积分范围" ,"desc" :"签到积分范围，例子:1-10,默认1-10"}
__param__ = {"required" :False ,"key" :"bot_point_config.symbol" ,"bool" :False ,"placeholder" :"积分符号","name" :"积分符号" ,"desc" :"积分符号,默认为：积分"}

import random
import string
from datetime import datetime,timedelta

async def user_sign(middleware):
    p = await middleware.bucket_get("bot_point_config","range","1-10")
    if p == "":
        p = "1-10"
    minp,maxp = p.split("-")
    return random.randint(int(minp),int(maxp))
async def sendt(message,middleware,t):
    await middleware.send_message(message.get("platform"),message.get("user_id"),t,message)


async def add_days_to_date(date_str, days):
    try:
        # 解析日期字符串
        original_date = datetime.strptime(date_str, '%Y-%m-%d')
        # 增加天数
        new_date = original_date + timedelta(days=days)
        # 格式化输出
        return new_date.strftime('%Y-%m-%d')
    except ValueError as e:
        return None


async def point(message,middleware):
    bucket_name = "bot_point"
    content = message.get("content")
    if content and content.startswith("积分"):
        user_id = message.get("user_id")
        platform = message.get("platform")
        ran_sign = await user_sign(middleware)
        today = datetime.now().strftime("%Y-%m-%d")
        is_admin = await middleware.is_admin(user_id)
        point_kc = await middleware.bucket_get("bot_point_config", "point_kc", {})
        user_point = await middleware.bucket_get(bucket_name, user_id, {})
        symbol = await middleware.bucket_get("bot_point_config", "symbol", "积分")
        if symbol == "":
            symbol = "积分"
        if "积分签到" in content:
            if user_point == {}:
                user_point = {"point":ran_sign,"sign_date":today,"qd":platform}
                await middleware.bucket_set(bucket_name,user_id,user_point)
            else:
                if user_point.get("sign_date") != today:
                    user_point["point"] += ran_sign
                    user_point["sign_date"] = today
                    await middleware.bucket_set(bucket_name,user_id,user_point)
                else:
                    return {
                        "content": "今天已经签到过了哦!",
                    }
            return {
                "content": f"签到成功，获得{ran_sign}{symbol}"
            }
        elif "积分查询" in content:
            if user_point == {}:
                return {
                    "content": f"您当前的积分为0{symbol}"
                }
            else:
                return {
                    "content": f"您当前的积分为{user_point.get('point')}{symbol}"
                }
        elif "积分库存" in content:
            if not is_admin:
                if point_kc is None or point_kc == {}:
                    return {
                        "content": "当前没有东西可兑换"
                    }
                kcs = ""
                i = 1
                for name,a in point_kc.items():
                    kcs += f"{i}、【{name}:{len(a['kc'])}】{a['use_point']}{symbol}\n"
                    i += 1
                await sendt(message, middleware, f"------积分库存为------\n{kcs}------\n输入序号可兑换\nq退出")
                num = await middleware.wait_for_input(message, 120000)
                if not num:
                    return {"content": "超时"}
                elif num == "q":
                    return {"content": "退出"}
                elif num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num)-1]
                    if user_point.get("point") >= point_kc[name]["use_point"] and point_kc[name]["kc"]:
                        await sendt(message, middleware,f'是否确定花费{point_kc[name]["use_point"]}积分兑换{name}/1，y确定、q取消')
                        is_ok = await middleware.wait_for_input(message, 120000)
                        if not is_ok:
                            return {"content": "超时"}
                        elif is_ok == "q":
                            return {"content": "取消"}
                        elif is_ok.lower() == "y":
                            user_point["point"] -= point_kc[name]["use_point"]
                            km = point_kc[name]["kc"][0]
                            point_kc[name]["kc"].remove(km)
                            await middleware.bucket_set(bucket_name,user_id,user_point)
                            await sendt(message,middleware,f"已消耗{point_kc[name]['use_point']}积分兑换【{name}】\n已私聊推送")
                            await middleware.push_to_user(platform, user_id, f"【{name}】您兑换的卡密为：{km}】")
                            return
                        else:
                            return {"content": "退出"}
                    else:
                        return {
                            "content": "您的积分或库存不足"
                        }
                else:
                    return {
                        "content": "输入错误"
                    }

            kcs = ""
            b = 1
            for name, a in point_kc.items():
                kcs += f"{b}、【{name}:{len(a['kc'])}】{a['use_point']}{symbol}\n"
                b += 1
            kcs += "------\n0、库存积分配置\n1、新增库存名\n2、上传库存\n3、删除指定数据\n4、删除库存名(包括数据)\n5、兑换\n------\n请输入序号,q退出"
            await sendt(message,middleware,kcs)
            user_in = await middleware.wait_for_input(message,120000)
            if not user_in:
                return {"content":"超时"}
            elif user_in == "q":
                return {"content":"退出"}
            if user_in == "0":
                msg = "请输入上面库存列表的序号,q退出"
                await sendt(message, middleware, msg)
                num = await middleware.wait_for_input(message, 120000)
                if not num:
                    return {"content": "超时"}
                elif num == "q":
                    return {"content": "退出"}
                if num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num) - 1]
                    await sendt(message, middleware,f'输入兑换当前库存的新积分数量(当前:{point_kc[name]["use_point"]}{symbol})')
                    is_ok = await middleware.wait_for_input(message, 120000)
                    if not is_ok:
                        return {"content": "超时"}
                    elif is_ok == "q":
                        return {"content": "取消"}
                    elif is_ok.isdigit():
                        point_kc[name]["use_point"] = int(is_ok)

                        await middleware.bucket_set(bucket_name, user_id, user_point)
                        await sendt(message, middleware, f"{name}消耗积分已修改为{is_ok}{symbol}")
                        return
                    else:
                        return {"content": "退出"}

                else:
                    return {"content": "输入错误"}


            elif user_in == "1":
                await sendt(message,middleware,"请输入库存名")
                name = await middleware.wait_for_input(message,120000)
                if not name:
                    return {"content":"超时"}
                if name in point_kc:
                    return {"content":"库存名已存在"}
                await sendt(message, middleware, "需要多少积分兑换")
                use_point = await middleware.wait_for_input(message, 120000)
                if not use_point:
                    return {"content":"超时"}
                if not use_point.isdigit() or "q" == use_point:
                    return {"content":"输入错误"}
                if point_kc == {}:
                    await middleware.bucket_set("bot_point_config","point_kc",{name:{"kc":[],"use_point":int(use_point)}})

                else:
                    point_kc[name] = {"kc":[],"use_point":int(use_point)}
                    await middleware.bucket_set("bot_point_config","point_kc",point_kc)
                await sendt(message, middleware, f"已创建库存{name}:{use_point}{symbol}")
                return
            elif user_in == "2":
                kcs = ""
                i = 1
                for name,a in point_kc.items():
                    kcs += f"【{i}】{name}:{len(a)}\n"
                    i += 1
                await sendt(message, middleware, f"{kcs}\n请输入库存名序号")
                num = await middleware.wait_for_input(message,120000)
                if not num:
                    return {"content":"超时"}
                elif num == "q":
                    return {"content": "退出"}
                if num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num)-1]
                    await sendt(message,middleware,f"请输入要上传的库存内容或者卡密，一行一个")
                    kcs = await middleware.wait_for_input(message,120000)
                    if not kcs:
                        return {"content":"超时"}
                    if not point_kc[name]["kc"]:
                        point_kc[name]["kc"] = kcs.split("\n")
                    else:
                        for i in kcs.split("\n"):
                            point_kc[name]["kc"].append(i)
                    lenkc = len(kcs.split('\n'))
                    await middleware.bucket_set("bot_point_config","point_kc",{name:{"kc":point_kc[name]["kc"],"use_point":point_kc[name]["use_point"]}})
                    await sendt(message,middleware,f"{name}已上传库存{lenkc}")
                    return
                else:
                    return {"content":"输入错误"}
            elif user_in == "3":
                kcs = ""
                i = 1
                for name, a in point_kc.items():
                    kcs += f"【{i}】{name}:{len(a)}\n"
                    i += 1
                await sendt(message, middleware, f"{kcs}\n请输入库存名序号")
                num = await middleware.wait_for_input(message, 120000)
                if not num:
                    return {"content": "超时"}
                elif num == "q":
                    return {"content": "退出"}
                if num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num) - 1]
                    await sendt(message, middleware, f"请输入要删除的库存内容或者卡密，一行一个")
                    kcs = await middleware.wait_for_input(message, 120000)
                    if not kcs:
                        return {"content": "超时"}
                    elif kcs == "q":
                        return {"content": "退出"}
                    else:
                        kcs = kcs.split("\n")
                        erro = ""
                        cg = 0
                        for a in kcs:
                            if a in point_kc[name]["kc"]:
                                point_kc[name]["kc"].remove(a)
                                cg += 1
                            else:
                                erro += f"{a}\n"
                        return {
                            "content": f"删除{cg}成功\n失败：{erro}"
                        }
                else:
                    return {"content": "输入错误"}
            elif user_in == "4":
                kcs = ""
                i = 1
                for name, a in point_kc.items():
                    kcs += f"【{i}】{name}:{len(a)}\n"
                    i += 1
                await sendt(message, middleware, f"{kcs}\n请输入序号，删除的库存名以及全部数据，q退出")
                num = await middleware.wait_for_input(message, 120000)
                if not num:
                    return {"content": "超时"}
                elif num == "q":
                    return {"content": "退出"}
                if num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num) - 1]
                    await sendt(message, middleware, f"确定删除？y确定，q退出")
                    is_ok = await middleware.wait_for_input(message, 120000)
                    if not is_ok:
                        return {"content": "超时"}
                    elif is_ok == "q":
                        return {"content": "退出"}
                    elif is_ok.lower() == "y":
                        del point_kc[name]
                        await middleware.bucket_set("bot_point_config","point_kc",point_kc)
                        await sendt(message, middleware, f"已删除{name}")
                        return
                else:
                    return {"content": "输入错误"}
            elif user_in == "5":
                msg = "请输入上面库存列表的序号,q退出"
                await sendt(message, middleware, msg)
                num = await middleware.wait_for_input(message, 120000)
                if not num:
                    return {"content": "超时"}
                elif num == "q":
                    return {"content": "退出"}
                if num.isdigit() and int(num) <= len(point_kc):
                    name = list(point_kc.keys())[int(num) - 1]
                    if user_point.get("point") >= point_kc[name]["use_point"] and point_kc[name]["kc"]:
                        await sendt(message, middleware,
                                    f'是否确定花费{point_kc[name]["use_point"]}{symbol}兑换{name}/1，y确定、q取消')
                        is_ok = await middleware.wait_for_input(message, 120000)
                        if not is_ok:
                            return {"content": "超时"}
                        elif is_ok == "q":
                            return {"content": "取消"}
                        elif is_ok.lower() == "y":
                            user_point["point"] -= point_kc[name]["use_point"]
                            km = point_kc[name]["kc"][0]
                            point_kc[name]["kc"].remove(km)
                            await middleware.bucket_set(bucket_name, user_id, user_point)
                            await sendt(message, middleware, f"已消耗{point_kc[name]['use_point']}{symbol}兑换{name}：{km}")
                            return
                        else:
                            return {"content": "退出"}
                    else:
                        return {
                            "content": f"您的{symbol}或库存不足"
                        }
                else:
                    return {"content": "输入错误"}
        elif "积分授权" in content:
            if not is_admin:
                return {"content": "无权限"}
            await sendt(message, middleware, "请输入要授权的id")
            id = await middleware.wait_for_input(message, 120000)
            if not id:
                return {"content": "超时"}
            await sendt(message, middleware, f"请输入要授权的{symbol}数量")
            point = await middleware.wait_for_input(message, 120000)
            if not point:
                return {"content": "超时"}
            elif not point.isdigit():
                return {"content": "输入错误"}
            old = await middleware.bucket_get(bucket_name, id,{})
            if old == {}:
                user_point = {"point": int(point), "sign_date": today, "qd": platform}
                await middleware.bucket_set(bucket_name, id, user_point)
            else:
                old["point"] += int(point)
                await middleware.bucket_set(bucket_name, id, old)

            return {"content":f"{id}增加{point}{symbol}成功"}
        return None
    elif content and content.startswith("卡密"):
        user_id = message.get("user_id")
        platform = message.get("platform")
        is_admin = await middleware.is_admin(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        kamis = await middleware.bucket_get("bot_kami_config","kamis",{})
        if "卡密查询" == content:
            await sendt(message, middleware, "请输入卡密")
            card = await middleware.wait_for_input(message, 120000)
            if not card:
                return {"content": "超时"}
            elif card == "q":
                return {"content": "退出"}
            else:
                if card in kamis:
                    data = kamis[card]
                    return {"content": f"{card}\n有效期:{data['date']}\n绑定ID:{data['use_id']}\n创建时间:{data['cr_date']}\n渠道:{data['qd']}\n项目:{data['item']}"}
                else:
                    return {"content": "卡密不存在"}

        elif "卡密生成" == content and is_admin:
            await sendt(message, middleware, "请输入要生成的卡密数量")
            num = await middleware.wait_for_input(message, 120000)
            if not num:
                return {"content": "超时"}
            elif num == "q":
                return {"content": "退出"}
            elif not num.isdigit():
                return {"content": "输入错误"}
            else:
                await sendt(message, middleware, "请输入卡密有效期")
                expire = await middleware.wait_for_input(message, 120000)
                if expire == "q":
                    return {"content": "退出"}
                elif not num:
                    return {"content": "超时"}
                elif not num.isdigit():
                    return {"content": "输入错误"}
                num = int(num)
                cds = ""
                for i in range(num):
                    card = "".join(random.sample(string.ascii_letters + string.digits, 16))
                    cds += f"{card}\n"
                    kamis[card] = {"date": await add_days_to_date(today,int(expire)), "use_id": "", "cr_date": today,"qd":"","item":""}
                await middleware.bucket_set("bot_kami_config","kamis",kamis)
                return {"content": f"生成{num}张卡密成功:{cds}"}

def register(middleware):
    middleware.register_message_handler(point)
