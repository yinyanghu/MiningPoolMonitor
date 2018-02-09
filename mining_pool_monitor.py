import requests
import json
import datetime
import time
import os

etn_wallet_address = 'etnkH3JcwEG4i2eApbeJk6fYMGmYAWc9yCZmVWEWdsa9XETkzWEY6o9M76AGhWUnrBVzuCor7vGSQHgxYLmdUGeeAaPih64cmM'
pas_wallet_address = '86646.2f6e24867ad0c6fd'

def request_data(url):
    r = requests.get(url).json()
    if r['status'] == True:
        return r['data']
    else:
        print(r)
        print("Error: " + url)
        return None

def format_hashrate(hashrate):
    hashrate = float(hashrate)
    unit_lst = [x + 'H/s' for x in ['', 'K', 'M', 'G', 'T', 'P']]
    unit = 0
    while hashrate >= 1000:
        unit += 1
        hashrate /= 1000
    return str(hashrate) + ' ' + unit_lst[unit]


class Worker:
    def __init__(self, data):
        self.id = data['id']
        self.rating = int(data['rating'])
        self.hashrate = float(data['hashrate'])
        self.lastshare = datetime.datetime.fromtimestamp(data['lastshare'])
        self.avg_h1 = float(data['h1'])
        self.avg_h3 = float(data['h3'])
        self.avg_h6 = float(data['h6'])
        self.avg_h12 = float(data['h12'])
        self.avg_h24 = float(data['h24'])

    def __str__(self):
        return self.id + ': ' \
        + 'Hashrate: ' + format_hashrate(self.hashrate) + ', ' \
        + '1 Hour Hashrate: ' + format_hashrate(self.avg_h1) + ', ' \
        + 'Last Share: ' + str(self.lastshare) + ', ' \
        + 'Rating: ' + str(self.rating)


class Payment:
    def __init__(self, data):
        self.amount = float(data['amount'])
        self.confirmed = bool(data['confirmed'])
        self.date = datetime.datetime.fromtimestamp(data['date'])

    def __str__(self):
        return 'Amount: ' + str(self.amount) + ', ' \
        + 'Date: ' + str(self.date) + ', ' \
        + 'Confirmed: ' + str(self.confirmed)



class Account:
    def __init__(self, pool, wallet_address):
        self.wallet_address = wallet_address
        self.pool = pool

        self.balance = 0
        self.unconfirmed_balance = 0
        self.current_hashrate = 0
        self.current_reported_hashrate = 0
        self.avg_hashrate = None

        self.workers = []

        self.payments = []
        self.total_payment = 0

    def update(self):
        url = self.pool.api + self.pool.coin + '/user/' + self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_general(data)

        url = self.pool.api + self.pool.coin + '/reportedhashrate/' + self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_reported_hashrate(data)

        url = self.pool.api + self.pool.coin + '/payments/' + self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_payments(data)

    def get_all_balance(self):
        return self.balance + self.unconfirmed_balance

    def get_hashrate(self):
        return float(self.avg_hashrate['h1'])

    def get_total_payment(self):
        return self.total_payment

    def __update_general(self, data):
        self.balance = float(data['balance'])
        self.unconfirmed_balance = float(data['unconfirmed_balance'])
        self.current_hashrate = float(data['hashrate'])
        self.avg_hashrate = data['avgHashrate']
        self.__update_workers(data['workers'])

    def __update_reported_hashrate(self, data):
        self.current_reported_hashrate = float(data)

    def __update_workers(self, data):
        self.workers = []
        for worker in data:
            self.workers.append(Worker(worker))
        self.workers.sort(key=lambda worker: worker.hashrate, reverse=True)

    def __update_payments(self, data):
        self.payments = []
        self.total_payment = 0
        for one in data:
            payment = Payment(one)
            self.payments.append(payment)
            self.total_payment += payment.amount


    def __str__(self):
        return 'Account: ' + self.wallet_address[:10] + '...' + self.wallet_address[-10:] + '\n' \
        + '--------------------------------------' + '\n' \
        + 'Balance: ' + str(self.balance) + '\n' \
        + 'Unconfirmed Balance: ' + str(self.unconfirmed_balance) + '\n' \
        + '\n' \
        + 'Hashrate: ' + '\n' \
        + '\t' + 'Current: ' + format_hashrate(self.current_hashrate) + '\n' \
        + '\t' + 'Current Reported: ' + format_hashrate(self.current_reported_hashrate) + '\n' \
        + '\t' + '1 Hour Average: ' + format_hashrate(self.avg_hashrate['h1']) + '\n' \
        + '\t' + '24 Hours Average: ' + format_hashrate(self.avg_hashrate['h24']) + '\n' \
        + '\n' \
        + 'Workers:' + '\n\t' \
        + '\n\t'.join([str(worker) for worker in self.workers]) + '\n' \
        + '\n' \
        + 'Payment:' + '\n' \
        + '\t' + 'Total Amount: ' + str(self.total_payment) + '\n\t' \
        + '\n\t'.join([str(payment) for payment in self.payments[:2]])


class Price:
    def __init__(self, pool):
        self.pool = pool

        self.usd = 0
        self.btc = 0

    def update(self):
        url = self.pool.api + self.pool.coin + '/prices'
        data = request_data(url)
        self.usd = float(data['price_usd'])
        self.btc = float(data['price_btc'])

    def get_usd_price(self):
        return self.usd

    def __str__(self):
        return 'Price:' + '\n' \
        + '--------------------------------------' + '\n' \
        + '\t' + 'USD: ' + str(self.usd) + '\n' \
        + '\t' + 'BTC: ' + str(self.btc)


class Estimation:
    def __init__(self, pool):
        self.pool = pool

        self.estimated_profit = 0
        self.hashrate = 0

        self.hour_coin = 0
        self.hour_usd = 0
        self.day_coin = 0
        self.day_usd = 0
        self.month_coin = 0
        self.month_usd = 0

        self.next_payment_time = 0

    def update(self, hashrate, estimated_profit, balance):
        self.hashrate = hashrate
        self.estimated_profit = estimated_profit

        url = self.pool.api + self.pool.coin + '/approximated_earnings/' + str(hashrate)
        data = request_data(url)
        # print(data)

        self.hour_coin = float(data['hour']['coins'])
        self.hour_usd = float(data['hour']['dollars'])
        self.day_coin = float(data['day']['coins'])
        self.day_usd = float(data['day']['dollars'])
        self.month_coin = float(data['month']['coins'])
        self.month_usd = float(data['month']['dollars'])

        self.next_payment_time = max(0, (self.pool.get_payment_limit() - balance) / self.hour_coin)

    def __str__(self):
        return 'Estimation:' + '\n' \
        + '--------------------------------------' + '\n' \
        + '\t' + 'Total: ' + str(self.estimated_profit) + ' USD' + '\n' \
        + '\t' + 'Next Payment: ' + str(self.next_payment_time) + ' hours' + '\n' \
        + '\t' + 'Hour: ' + str(self.hour_coin) + ' (' + str(self.hour_usd) + ' USD)' + '\n' \
        + '\t' + 'Day: ' + str(self.day_coin) + ' (' + str(self.day_usd) + ' USD)' + '\n' \
        + '\t' + 'Month: ' + str(self.month_coin) + ' (' + str(self.month_usd) + ' USD)'


class NanoPool:
    def __init__(self, name, coin, wallet_address):
        self.api = 'https://api.nanopool.org/v1/'
        self.name = name
        self.coin = coin
        self.payment_limit = self.__get_payment_limit(wallet_address)

        self.hashrate = 0

        self.account = Account(self, wallet_address)
        self.price = Price(self)

        self.estimation = Estimation(self)

    def __get_payment_limit(self, wallet_address):
        url = self.api + self.coin + '/usersettings/' + wallet_address
        data = request_data(url)
        return float(data['payout'])


    def update(self):
        url = self.api + self.coin + '/pool/hashrate'
        self.hashrate = float(request_data(url))

        self.account.update()
        self.price.update()

        self.estimation.update(self.account.get_hashrate(), self.__get_profit(), self.account.get_all_balance())

    def get_payment_limit(self):
        return self.payment_limit

    def __get_profit(self):
        return self.account.get_total_payment() * self.price.get_usd_price()

    def __str__(self):
        return self.name + '\n' \
        + '===========' + '\n' \
        + '\n' \
        + 'Pool:' + '\n' \
        + '--------------------------------------' + '\n' \
        + '\t' + 'Hashrate: ' + format_hashrate(self.hashrate) + '\n' \
        + '\t' + 'Payment Limit: ' + str(self.payment_limit) + '\n' \
        + '\n' \
        + str(self.account) + '\n' \
        + '\n' \
        + str(self.price) + '\n' \
        + '\n' \
        + str(self.estimation)


class Ethermine:
    def __init__(self):
        pass




etn_nanopool = NanoPool('Electroneum (ETN)','etn', etn_wallet_address)
pas_nanopool = NanoPool('PascalCoin (PAS)','pasc', pas_wallet_address)

def etn():
    etn_nanopool.update()
    print(str(etn_nanopool))

def pas():
    pas_nanopool.update()
    print(str(pas_nanopool))

if __name__ == '__main__':
    while True:
        os.system('clear')
        etn()
        time.sleep(30)
        os.system('clear')
        pas()
        time.sleep(30)
