import codecs
import json
import logging
import random
import re
import time
import traceback

import requests
from requests.exceptions import ConnectionError


class Login(object):
    host = "http://210.77.16.21/"
    logout_url = host + "eportal/gologout.jsp"
    ePortalUrl = host + "eportal/InterFace.do?method="

    def _print_log(self, response):
        if logging.root.level == logging.DEBUG:
            self.dumps_response(response)
        logging.info("[#] %s %s", response.status_code, response.url)

    def print_log(self):
        for response in self.response.history:
            self._print_log(response)
        self._print_log(self.response)
         
    def dumps_response(self, response):
        codecs.open("{}.html".format(self.uid), "w", "utf-8").write(response.text)
        codecs.open("{}_rqh.json".format(self.uid), "w", "utf-8").write(
            json.dumps(response.request.headers.__dict__, indent=4)
        )
        codecs.open("{}_rth.json".format(self.uid), "w", "utf-8").write(
            json.dumps(response.headers.__dict__, indent=4)
        )
        self.uid += 1

    def __init__(self, account, password="ucas", reserved_flow_limit=512):
        self.uid = 1
        self.con = requests.Session()
        self.con.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.91 Safari/537.36"
        self.con.cookies["EPORTAL_USER_GROUP"]="%E4%B8%80%E5%8D%A1%E9%80%9A%E5%B8%90%E5%8F%B7"
        self.response = None
        self.self_url = None
        self.money = None
        self.left_flow = None
        self.online_count = None
        self.login_type = 3
        self.account = account
        self.password = password
        self.data = None
        self.reserved_flow_limit = reserved_flow_limit
        self.get_page(Login.host)
        # logging.info("%s, %s",tmp.url, len(tmp.text))
        self.user_index = self.response.url.split("=")[-1]
        self.logout()  # logout the origin account
        self.get_page(Login.logout_url)
        # logging.info("%s, %s", tmp.text, tmp.url)
        self.index_url = self.response.url
        self.query_string = self.index_url.split("?")[-1]
        # loggin.info("%s, %s", self.index_url, self.user_index)

    @property
    def message(self):
        if self.data is None:
            return ""
        else:
            return self.data.get("message", "").strip()

    def get_json_page(self, url):
        self.response = self.get_page(url)
        self.response.encoding = "utf-8"
        self.data = self.response.json()
        return self.data

    def set_referer(self, referer):
        if referer and self.response is not None:
            self.con.headers["Referer"] = self.response.url
        if not referer and "Referer" in self.con.headers:
            del self.con.headers["Referer"]
    
    def set_origin(self, origin="http://210.77.16.21"):
        if "Origin" in self.con.headers and origin is None:
            del self.con.headers["Origin"]
        if origin is not None:
            self.con.headers["Origin"] = origin

    def get_page(self, url, referer=True):
        logging.info("[#] GET : %s", url)
        self.set_referer(referer)
        self.set_origin()
        self.response = self.con.get(url)
        # logging.info(self.response.text)
        self.print_log()
        return self.response

    def post_page(self, url, content, referer=True):
        self.set_referer(referer)
        self.set_origin()
        logging.info("[#] POST: %s\n %s", url, content)
        try:
            self.response = self.con.post(url, data=content)
            self.response.encoding = "utf-8"
            # logging.info(self.response.text)
            self.data = self.response.json()
        except ConnectionError as e:
            logging.exception("[*] Exception: url: %s, %s", url, e)
            traceback.print_exc()
            self.data["result"] = "failed"
        except Exception as e:
            logging.exception("[!] Exception: %s", e)
            self.data = {}
        self.print_log()
        return self.data

    def ePortal_post(self, method, content):
        self.post_page(Login.ePortalUrl + method, content)
        return self.data

    def login(self, account=None, passwd="ucas"):
        if account is None:
            account, passwd = self.account, self.password

        data = {
            "userId": account,
            "password": passwd,
            "service": "",
            "queryString": self.query_string,
            "operatorPwd": "",
            "validcode": "",
            "operatorUserId": ""
        }
        try:
            self.ePortal_post("login", data)
        except:
            traceback.print_exc()
            return False
        self.user_index = self.data["userIndex"]
        return self.data["result"] == "success"

    def logout_by_userid_and_password(self, user_id, password):
        self.ePortal_post("logoutByUserIdAndPass",
                          {"userId": user_id, "pass": password})
        return self.data["result"] == "success"

    def logout(self):
        self.ePortal_post("logout", {"userIndex": self.user_index})
        return self.data["result"] == "success"

    def keep_alive(self):
        self.ePortal_post("keepalive", {"userIndex": self.user_index})
        return self.data["result"] == "success"

    def get_online_user_info(self):
        if self.user_index:
            self.get_page(
                "http://210.77.16.21/eportal/success.jsp?userIndex=" +
                self.user_index)
        content = {"userIndex": self.user_index}
        url = Login.ePortalUrl + "getOnlineUserInfo"
        self.post_page(url, content)
        self.self_url = self.data["selfUrl"]
        allinfos = self.data["ballInfo"]
        self.login_type = self.data["loginType"]
        if allinfos:
            values = [float(dct["value"]) for dct in json.loads(allinfos)]
            if len(values) < 3:
                logging.info(u"[*] length of values less than 3")
            self.money = values[0]
            self.left_flow = values[1] / 1024.0 / 1024.0
            self.online_count = values[2]
        return self.money, self.left_flow, self.online_count

    def print_account_infos(self):
        logging.info(
            u"[#] %s %s %s %s %s %s %s %s %s",
            time.strftime("%H:%M:%S", time.localtime()),
            self.account, u"¥:", self.money,
            "Flow:", "%.2fMB" % self.left_flow,
            "Users:", int(self.online_count), self.message
        )

    def log_users(self):
        logging.warning("[!] %s users online at the same time, so logout",
                        self.online_count)

    def log_flow_limit(self):
        logging.warning(
            "[!] %s MB Left flow is less than min reserved flow limit %s MB",
            self.left_flow, self.reserved_flow_limit)

    def fresh_online_user_info(self):
        self.ePortal_post("freshOnlineUserInfo",
                          {"userIndex": self.user_index})
        for key in self.data:
            logging.info(u"%s %s %s", key, ":", self.data[key])
        logging.info(u"%s %s", self.data["maxFlow"], self.data["accountFee"])

    def get_user_infos(self):
        if not self.self_url:
            self.get_online_user_info()

        conn = requests.Session()
        conn.get(self.self_url)
        ret = conn.get("http://121.195.186.149/selfservice/module/userself/web/consume.jsf")
        fee = "".join(
            re.findall(r'<td class=\"contextDate\">(.+)\..+</td>', ret.text))
        res = re.findall(r':(.+)MB / ([0-9\.]+) GB', ret.text)
        used = res[0][0].replace(" ", "")
        if "GB" in used:
            used = [float(n) for n in used.split("GB")]
            used = used[0] * 1024 + used[1]
        else:
            used = float(used)
        all_flow = float(res[0][1]) * 1024
        return all_flow - used, float(fee)

    def do_keep_alive(self):
        retry_count, interval = 3, 0
        while retry_count > 0:
            while self.keep_alive():
                retry_count = 3
                # print self.data["result"], self.data["message"]
                if interval == 0:
                    for i in range(3):
                        try:
                            self.get_online_user_info()
                            break
                        except Exception:
                            traceback.print_exc()
                            time.sleep(5)

                    if (self.left_flow > self.reserved_flow_limit and
                            self.online_count < 2):
                        self.print_account_infos()
                    else:
                        if self.online_count > 1:
                            self.log_users()
                        else:
                            self.log_flow_limit()
                        return self.logout()
                interval = (5 + interval) % 60
                time.sleep(5)
            retry_count -= 1
        return False

    def register_network(self):
        method = "registerNetWorkProtocol"
        data = {"userId": self.account}
        self.ePortal_post(method, data)

    def keep_running(self, retry_count=3):
        if retry_count > 0 and self.login(self.account, self.password):
            self.get_user_infos()
            fee, rest_flow, user_count = self.get_online_user_info()
            if rest_flow < self.reserved_flow_limit:
                self.log_flow_limit()
                logging.warning(
                    "[!] %s MB Left flow less than min reserved limit %s MB",
                    self.left_flow, self.reserved_flow_limit)
                return self.logout()
            logging.info(u"[#] Account %s Login Succeed! %s", self.account,
                         self.message)
        else:
            logging.warning(u"[!] Account %s Login Failed! %s", self.account,
                            self.message)
            flag = u"用户未确认网络协议书"
            if self.message.find(flag) == -1:
                return False
            self.register_network()
            self.register_network()
            self.login(self.account, self.password)
        if not self.do_keep_alive():
            return self.keep_running(retry_count - 1)


def check_account(accounts):
    users = []
    for user, password in accounts:
        ucas = Login(user, password)
        if ucas.login(user, password):
            users.append(user)
            ucas.logout()
            print user
    with open("users.txt", "w") as fl:
        fl.write("\n".join(users))
    print "\n".join(users)


def load_accounts(file_name="./accounts.txt"):
    return [
        (line.strip().split(" ")) for line in open(file_name, "r").readlines()
    ]



def test():
    logging.root.setLevel(logging.DEBUG)

    accounts = load_accounts("/Users/kean/tools/accounts.txt")
    user, passwd = accounts[-2][0], accounts[-2][1]
    h = Login(user, passwd)
    h.login()


def main():
    accounts = load_accounts()
    random.shuffle(accounts)

    for account, password in accounts:
        user = Login(account, password, 1024)
        user.keep_running(3)
    print "Oops! It seems that you've tried all the accounts"
    print "You need more new accounts, Kean may be glad to help you"


if __name__ == "__main__":
    logging.root.setLevel(logging.INFO)
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print "KeyboardInterrupt, Bye!"
            break
        except Exception as e:
            logging.exception("[!] Exception: %s", e)
            time.sleep(10)
