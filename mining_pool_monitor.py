import requests
import datetime
import time
import os

etn_wallet_address = 'etnkH3JcwEG4i2eApbeJk6fYMGmYAWc9yCZmVWEWdsa9XETkzWEY6o9M76AGhWUnrBVzuCor7vGSQHgxYLmdUGeeAaPih64cmM'
pas_wallet_address = '86646.2f6e24867ad0c6fd'
eth_wallet_address = '45f410e92683dAE322d91F2C8b26193b0FC3464D'


def request_data(url):
    r = requests.get(url).json()
    if r['status']:
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
    def __init__(self, name, rating, hashrate, lastshare, avg_hashrate):
        self.name = name
        self.rating = rating
        self.hashrate = hashrate
        self.lastshare = lastshare
        self.avg_hashrate = avg_hashrate

    def __str__(self):
        return self.id + ': ' \
            + 'Hashrate: ' + format_hashrate(self.hashrate) + ', ' \
            + '1 Hour Hashrate: ' + format_hashrate(self.avg_hashrate['h1']) + ', ' \
            + 'Last Share: ' + str(self.lastshare) + ', ' \
            + 'Rating: ' + str(self.rating)


class Payment:
    def __init__(self, amount, confirmed, date):
        self.amount = amount
        self.confirmed = confirmed
        self.date = date

    def __str__(self):
        return 'Amount: ' + str(self.amount) + ', ' \
            + 'Date: ' + str(self.date) + ', ' \
            + 'Confirmed: ' + str(self.confirmed)


class Account:
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address

        self.balance = 0
        self.unconfirmed_balance = 0
        self.current_hashrate = 0
        self.current_reported_hashrate = 0
        self.avg_hashrate = None

        self.workers = []

        self.payments = []
        self.total_payment = 0

    def get_all_balance(self):
        return self.balance + self.unconfirmed_balance

    def get_hashrate(self):
        return float(self.avg_hashrate['h1'])

    def get_total_payment(self):
        return self.total_payment

    def update(self, balance, unconfirmed_balance, current_hashrate, current_reported_hashrate, avg_hashrate):
        self.balance = balance
        self.unconfirmed_balance = unconfirmed_balance
        self.current_hashrate = current_hashrate
        self.current_reported_hashrate = current_reported_hashrate
        self.avg_hashrate = avg_hashrate

    def update_workers(self, workers):
        self.workers = workers

    def update_payments(self, payments):
        self.payments = payments

        self.total_payment = 0
        for payment in payments:
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
    def __init__(self):
        self.usd = 0
        self.btc = 0

    def update(self, usd, btc):
        self.usd = usd
        self.btc = btc

    def get_usd_price(self):
        return self.usd

    def __str__(self):
        return 'Price:' + '\n' \
            + '--------------------------------------' + '\n' \
            + '\t' + 'USD: $' + str(self.usd) + '\n' \
            + '\t' + 'BTC: ' + str(self.btc)


class Estimation:
    def __init__(self):
        self.estimated_profit = 0
        self.hashrate = 0

        self.hour_coin = 0
        self.hour_usd = 0
        self.day_coin = 0
        self.day_usd = 0
        self.month_coin = 0
        self.month_usd = 0

        self.next_payment_time = 0

    def update(self, hashrate, estimated_profit, balance, hour_coin, hour_usd, day_coin, day_usd, month_coin, month_usd):
        self.hashrate = hashrate
        self.estimated_profit = estimated_profit

        self.hour_coin = hour_coin
        self.hour_usd = hour_usd
        self.day_coin = day_coin
        self.day_usd = day_usd
        self.month_coin = month_coin
        self.month_usd = month_usd

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

        self.estimation = Estimation()

    def __get_payment_limit(self, wallet_address):
        url = self.api + self.coin + '/usersettings/' + wallet_address
        data = request_data(url)
        return float(data['payout'])


    def update(self):
        url = self.pool.api + self.pool.coin + '/user/' + self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_general(data)

        url = self.pool.api + self.pool.coin + '/reportedhashrate/'+ self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_reported_hashrate(data)

        url = self.pool.api + self.pool.coin + '/payments/' + self.wallet_address
        data = request_data(url)
        # print(data)
        self.__update_payments(data)

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
        for one in data:
            name = one['id']
            rating = int(one['rating'])
            hashrate = float(one['hashrate'])
            lastshare = datetime.datetime.fromtimestamp(one['lastshare'])
            avg_h1 = float(one['h1'])
            avg_h3 = float(one['h3'])
            avg_h6 = float(one['h6'])
            avg_h12 = float(one['h12'])
            avg_h24 = float(one['h24'])
            worker = Worker(id, name, rating, hashrate, lastshare, avg_h1, avg_h3, avg_h6, avg_h12, avg_h24)
            self.workers.append(worker)
        self.workers.sort(key=lambda worker: worker.hashrate, reverse=True)

    def __update_payments(self, data):
        for one in data:
            amount = float(data['amount'])
            confirmed = bool(data['confirmed'])
            date = datetime.datetime.fromtimestamp(data['date'])
            payment = Payment(amount, confirmed, date)

    def update(self):
        self.__update_pool_hashrate()
        self.account.update()
        self.__update_price()
        self.__update_estimation()

    def __update_pool_hashrate(self):
        url = self.api + self.coin + '/pool/hashrate'
        self.hashrate = float(request_data(url))

    def __update_price(self):
        url = self.api + self.coin + '/prices'
        data = request_data(url)
        usd = float(data['price_usd'])
        btc = float(data['price_btc'])
        self.price.update(usd, btc)

    def __update_estimation(self):
        current_hashrate = self.account.get_hashrate()
        url = self.api + self.coin + '/approximated_earnings/' + str(current_hashrate)
        data = request_data(url)

        hour_coin = float(data['hour']['coins'])
        hour_usd = float(data['hour']['dollars'])
        day_coin = float(data['day']['coins'])
        day_usd = float(data['day']['dollars'])
        month_coin = float(data['month']['coins'])
        month_usd = float(data['month']['dollars'])

        self.estimation.update(current_hashrate, self.__get_profit(), self.account.get_all_balance(), \
            hour_coin, hour_usd, day_coin, day_usd, month_coin, month_usd)

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


class Network:
    def __init__(self):



class Ethermine:
    def __init__(self, name, wallet_address):
        self.api = 'http://api.ethermine.org'
        self.name = name

        self.hashrate = 0
        self.price = Price()

    def update(self):
        url = self.api + "/poolStats"
        data = request_data(url)
        self.hashrate = data['poolStats']['hashRate']
        self.price.update(data['price']['usd'], data['price']['btc'])

    def __str__(self):
        return self.name + '\n' \
            + '===========' + '\n' \
            + '\n' \
            + 'Pool:' + '\n' \
            + '--------------------------------------' + '\n' \
            + '\t' + 'Hashrate: ' + format_hashrate(self.hashrate) + '\n' \
            + '\n' \
            + str(self.price) + '\n' \
            + '\n'




etn_nanopool = NanoPool('Electroneum (ETN)', 'etn', etn_wallet_address)
pas_nanopool = NanoPool('PascalCoin (PAS)', 'pasc', pas_wallet_address)
eth_ethermine = Ethermine('Ethereum (ETH)', eth_wallet_address)


def etn():
    etn_nanopool.update()
    print(str(etn_nanopool))


def pas():
    pas_nanopool.update()
    print(str(pas_nanopool))


def eth():
    eth_ethermine.update()
    print(str(eth_ethermine))


if __name__ == '__main__':
    eth()
#    while True:
#        os.system('clear')
#        etn()
#        time.sleep(30)
#        os.system('clear')
#        pas()
#        time.sleep(30)
