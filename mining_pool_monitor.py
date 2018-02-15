import requests
import datetime
import time
import os

etn_wallet_address = 'etnkH3JcwEG4i2eApbeJk6fYMGmYAWc9yCZmVWEWdsa9XETkzWEY6o9M76AGhWUnrBVzuCor7vGSQHgxYLmdUGeeAaPih64cmM'
pas_wallet_address = '86646.2f6e24867ad0c6fd'
eth_wallet_address = '45f410e92683dAE322d91F2C8b26193b0FC3464D'

text_normal = '\033[0m'

def bold(text):
    return '\033[1m' + text + text_normal


def white(text):
    return '\033[97m' + text + text_normal


def red(text):
    return '\033[91m' + text + text_normal


def yellow(text):
    return '\033[93m' + text + text_normal


def cyan(text):
    return '\033[96m' + text + text_normal


def purple(text):
    return '\033[95m' + text + text_normal


def request_data(url):
    r = requests.get(url).json()
    if r['status']:
        return r['data']
    else:
        print(r)
        print('Error: ' + url)
        return None


def format_number(number):
    unit_lst = [x for x in ['', 'K', 'M', 'G', 'T', 'P']]
    unit = 0
    while number >= 1000:
        unit += 1
        number /= 1000
    return '%.3f' % number + ' ' + unit_lst[unit]


def format_hashrate(hashrate):
    return format_number(float(hashrate)) + 'H/s'


def format_wallet_address(address):
    if len(address) > 30:
        return address[:10] + '...' + address[-10:]
    else:
        return address


def convert_to_eth(amount):
    if amount is None:
        return 0
    else:
        return amount / 1e18


class Worker:
    def __init__(self, name, hashrate, last_seen, rating=None,
                 avg_hashrate=None, reported_hashrate=None,
                 valid_share=None, invalid_share=None, stale_share=None):
        self.name = name
        self.rating = rating
        self.hashrate = hashrate
        self.last_seen = last_seen
        self.avg_hashrate = avg_hashrate
        self.reported_hashrate = reported_hashrate
        self.valid_share = valid_share
        self.invalid_share =invalid_share
        self.stale_share = stale_share

    def __str__(self):
        s = bold(yellow('%15s: ' % (self.name)))
        s += 'Hashrate: %s (effective)' % red(format_hashrate(self.hashrate))
        if self.reported_hashrate is not None:
            s += ', %s (reported)' % red(format_hashrate(self.reported_hashrate))
        if self.avg_hashrate is not None:
            if 'h1' in self.avg_hashrate:
                s += ', %s (1 hour)' % format_hashrate(self.avg_hashrate['h1'])
            if 'h24' in self.avg_hashrate:
                s += ', %s (1 day)' % format_hashrate(self.avg_hashrate['h24'])

        s += ';\n' + (' ' * 17) + 'Last Seen: ' + str(self.last_seen)
        if self.rating is not None:
            s += '; Rating: ' + str(self.rating)
        if (self.valid_share is not None) and (self.invalid_share is not None) and (self.stale_share is not None):
            s += '; Share: %d, %d, %d' % (self.valid_share, self.invalid_share, self.stale_share)

        return s


class Payment:
    def __init__(self, amount, confirmed, date):
        self.amount = amount
        self.confirmed = confirmed
        self.date = date
        self.duration = None

    def update_duration(self, duration):
        self.duration = duration

    def __str__(self):
        return 'Amount: %.10f, Date: %s, Duration: %.2f hours, Confirmed: %s' % (self.amount, str(self.date), self.duration, str(self.confirmed))


class Account:
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address

        self.balance = 0
        self.unconfirmed_balance = None
        self.current_hashrate = 0
        self.current_reported_hashrate = None
        self.avg_hashrate = None

        self.last_seen = None
        self.valid_share = None
        self.invalid_share = None
        self.stale_share = None
        self.valid_percent = None
        self.invalid_percent = None
        self.stale_percent = None

        self.active_worker = None
        self.workers = None

        self.payments = None
        self.total_payment = None

    def get_all_balance(self):
        total = self.balance
        if self.unconfirmed_balance is not None:
            total += self.unconfirmed_balance
        return total

    def get_hashrate(self):
        return float(self.avg_hashrate['h1'])

    def get_total_payment(self):
        return self.total_payment

    def update(self, balance, current_hashrate, unconfirmed_balance=None,
               current_reported_hashrate=None, avg_hashrate=None,
               last_seen=None,
               valid_share=None, invalid_share=None, stale_share=None,
               active_worker=None):
        self.balance = balance
        self.unconfirmed_balance = unconfirmed_balance
        self.current_hashrate = current_hashrate
        self.current_reported_hashrate = current_reported_hashrate
        self.avg_hashrate = avg_hashrate
        self.last_seen = last_seen
        self.valid_share = valid_share
        self.invalid_share = invalid_share
        self.stale_share = stale_share
        if (valid_share is not None) and (invalid_share is not None) and (stale_share is not None):
            total_share = valid_share + invalid_share + stale_share
            self.valid_percent = valid_share / total_share * 100.0
            self.invalid_percent = invalid_share / total_share * 100.0
            self.stale_percent = stale_share / total_share * 100.0
        self.active_worker = active_worker

    def update_workers(self, workers):
        self.workers = workers

    def update_payments(self, payments):
        for i in range(len(payments) - 1):
            diff = payments[i].date - payments[i + 1].date
            hours = diff.seconds / 3600 + diff.days * 24
            payments[i].update_duration(hours)
        self.payments = payments

        self.total_payment = 0
        for payment in payments:
            self.total_payment += payment.amount

    def __str__(self):
        s = bold(white('Account: ' + format_wallet_address(self.wallet_address))) + '\n'
        s += '\t' + bold(purple('Balance: %.10f' % (self.balance)))
        if self.unconfirmed_balance is not None:
            s += '\t' + 'Unconfirmed Balance: %.10f' % (self.unconfirmed_balance)
        if self.last_seen is not None:
            s += '\t' + 'Last Seen: ' + str(self.last_seen)
        s += '\n' + '\n'
        s += bold(white('Hashrate:')) + '\n'
        s += '\t' + 'Current: ' + red(format_hashrate(self.current_hashrate))
        if self.current_reported_hashrate is not None:
            s += '\t' + 'Current Reported: ' \
                + red(format_hashrate(self.current_reported_hashrate))
        if self.avg_hashrate is not None:
            if 'h1' in self.avg_hashrate:
                s += '\t' + '1 Hour Average: ' \
                    + format_hashrate(self.avg_hashrate['h1'])

            if 'h24' in self.avg_hashrate:
                s += '\t' + '1 Day Average: ' \
                    + format_hashrate(self.avg_hashrate['h24'])
        s += '\n'
        if (self.valid_share is not None) and (self.invalid_share is not None) and (self.stale_share is not None):
            s += '\t' + 'Valid Share: %d (%.2f%%)' % (self.valid_share, self.valid_percent)
            s += '\t' + 'Invalid Share: %d (%.2f%%)' % (self.invalid_share, self.invalid_percent)
            s += '\t' + 'Stale Share: %d (%.2f%%)' % (self.stale_share, self.stale_percent) + '\n'
        s += '\n'
        s += bold(white('Workers:'))
        if self.active_worker is not None:
            s += ' ' + cyan(bold(str(self.active_worker) + ' Active'))
        s += '\n'
        s += '\n'.join([str(worker) for worker in self.workers]) + '\n'
        s += '\n'
        s += bold(white('Payment:')) + '\n'
        s += '\t' + bold(yellow('Total Amount: ' + str(self.total_payment))) + '\n'
        s += '\t' + '\n\t'.join([str(payment) for payment in self.payments[:4]])
        return s


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
        return bold(white('Price:')) + '\n' \
            + '\t' + 'USD: $' + str(self.usd) + ',' \
            + '\t' + 'BTC: ' + str(self.btc)


class Estimation:
    def __init__(self, payment_limit):
        self.payment_limit = payment_limit

        self.estimated_profit = 0
        self.hashrate = 0

        self.hour_coin = 0
        self.hour_usd = 0
        self.day_coin = 0
        self.day_usd = 0
        self.month_coin = 0
        self.month_usd = 0

        self.next_payment_time = 0

    def update(self, hashrate, estimated_profit, balance,
               hour_coin, hour_usd, day_coin, day_usd, month_coin, month_usd):
        self.hashrate = hashrate
        self.estimated_profit = estimated_profit

        self.hour_coin = hour_coin
        self.hour_usd = hour_usd
        self.day_coin = day_coin
        self.day_usd = day_usd
        self.month_coin = month_coin
        self.month_usd = month_usd

        self.next_payment_time = max(0, (self.payment_limit - balance) / self.hour_coin)

    def update_per_min(self, estimated_profit, balance,
                       minute_coin, minute_usd):
        self.estimated_profit = estimated_profit

        self.hour_coin = minute_coin * 60.0
        self.hour_usd = minute_usd * 60.0
        self.day_coin = self.hour_coin * 24.0
        self.day_usd = self.hour_usd * 24.0
        self.month_coin = self.day_coin * 30.0
        self.month_usd = self.day_usd * 30.0

        self.next_payment_time = (self.payment_limit - balance) / self.hour_coin

    def __str__(self):
        s = bold(white('Estimation:')) + '\n'
        s += '\t' + bold(yellow('Total: $%.2f' % self.estimated_profit)) + '\n'
        s += '\t' + 'Hour: %.10f ($%.2f)' % (self.hour_coin, self.hour_usd)
        s += '\t' + 'Day: %.10f ($%.2f)' % (self.day_coin, self.day_usd)
        s += '\t' + 'Month: %.10f ($%.2f)' % (self.month_coin, self.month_usd) + '\n'
        s += '\t' + bold(red('Next Payment: %.2f hours' % self.next_payment_time))
        return s


class Network:
    def __init__(self):
        self.hashrate = 0
        self.block_time = 0
        self.difficulty = 0

    def update(self, hashrate, block_time, difficulty):
        self.hashrate = hashrate
        self.block_time = block_time
        self.difficulty = difficulty

    def __str__(self):
        s = bold(white('Network:')) + '\n'
        s += '\t' + 'Hashrate: ' + format_hashrate(self.hashrate) + '\n'
        s += '\t' + 'Block Time: %.1fs' % self.block_time + '\n'
        s += '\t' + 'Difficulty: ' + format_number(self.difficulty)
        return s


class NanoPool:
    def __init__(self, name, coin, wallet_address):
        self.api = 'https://api.nanopool.org/v1/'
        self.name = name
        self.coin = coin
        self.wallet_address = wallet_address
        self.payment_limit = self.__update_payment_limit()

        self.hashrate = 0

        self.account = Account(wallet_address)
        self.price = Price()

        self.estimation = Estimation(self.payment_limit)

    def update(self):
        self.__update_pool_hashrate()
        self.__update_account()
        self.__update_price()
        self.__update_estimation()

    def __update_payment_limit(self):
        url = self.api + self.coin + '/usersettings/' + self.wallet_address
        data = request_data(url)
        return float(data['payout'])

    def __update_account(self):
        url = self.api + self.coin + '/reportedhashrate/' + self.wallet_address
        data = request_data(url)
        current_reported_hashrate=float(data)

        url = self.api + self.coin + '/user/' + self.wallet_address
        data = request_data(url)

        self.account.update(
            balance=float(data['balance']),
            unconfirmed_balance=float(data['unconfirmed_balance']),
            current_reported_hashrate=current_reported_hashrate,
            current_hashrate=float(data['hashrate']),
            avg_hashrate=data['avgHashrate'])

        self.__update_account_workers(data['workers'])

        self.__update_account_payments()

    def __update_account_workers(self, data):
        workers = []
        for one in data:
            worker = Worker(
                name=one['id'],
                rating=int(one['rating']),
                hashrate=float(one['hashrate']),
                last_seen=datetime.datetime.fromtimestamp(one['lastshare']),
                avg_hashrate=one)
            workers.append(worker)
        workers.sort(key=lambda worker: worker.hashrate, reverse=True)
        self.account.update_workers(workers)

    def __update_account_payments(self):
        url = self.api + self.coin + '/payments/' + self.wallet_address
        data = request_data(url)
        payments = []
        for one in data:
            payment = Payment(
                float(one['amount']),
                bool(one['confirmed']),
                datetime.datetime.fromtimestamp(one['date']))
            payments.append(payment)

        self.account.update_payments(payments)

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

        self.estimation.update(
            current_hashrate,
            self.__get_profit(),
            self.account.get_all_balance(),
            float(data['hour']['coins']),
            float(data['hour']['dollars']),
            float(data['day']['coins']),
            float(data['day']['dollars']),
            float(data['month']['coins']),
            float(data['month']['dollars']))

    def __get_profit(self):
        return self.account.get_total_payment() * self.price.get_usd_price()

    def __str__(self):
        s = bold(cyan(self.name)) + '\n'
        s += bold(cyan('==================')) + '\n'
        s += '\n'
        s += bold(white('Pool:')) + '\n'
        s += '\t' + 'Hashrate: ' + format_hashrate(self.hashrate) + '\n'
        s += '\t' + 'Payment Limit: ' + str(self.payment_limit) + '\n'
        s += '\n'
        s += str(self.account) + '\n'
        s += '\n'
        s += str(self.price) + '\n'
        s += '\n'
        s += str(self.estimation)
        return s


class Ethermine:
    def __init__(self, name, wallet_address):
        self.api = 'http://api.ethermine.org'
        self.name = name
        self.wallet_address = wallet_address
        self.payment_limit = self.__update_payment_limit()

        self.hashrate = 0
        self.account = Account(wallet_address)
        self.price = Price()
        self.network = Network()
        self.estimation = Estimation(self.payment_limit)

    def update(self):
        self.__update_pool_and_price()
        self.__update_network()
        self.__update_account_and_estimation()

    def __update_payment_limit(self):
        url = self.api + '/miner/' + self.wallet_address + '/settings'
        data = request_data(url)
        return convert_to_eth(float(data['minPayout']))

    def __update_account_and_estimation(self):
        url = self.api + '/miner/' + self.wallet_address + '/currentStats'
        data = request_data(url)
        self.account.update(
            balance=convert_to_eth(data['unpaid']),
            unconfirmed_balance=convert_to_eth(data['unconfirmed']),
            current_hashrate=float(data['currentHashrate']),
            current_reported_hashrate=float(data['reportedHashrate']),
            avg_hashrate={'h24': float(data['averageHashrate'])},
            last_seen=datetime.datetime.fromtimestamp(data['lastSeen']),
            valid_share=int(data['validShares']),
            invalid_share=int(data['invalidShares']),
            stale_share=int(data['staleShares']),
            active_worker=int(data['activeWorkers']))

        self.__update_account_workers()
        self.__update_account_payments()

        self.estimation.update_per_min(
            self.__get_profit(),
            self.account.get_all_balance(),
            data['coinsPerMin'],
            data['usdPerMin'])


    def __update_account_workers(self):
        url = self.api + '/miner/' + self.wallet_address + '/workers'
        data = request_data(url)
        workers = []
        for one in data:
            worker = Worker(
                name=one['worker'],
                last_seen=datetime.datetime.fromtimestamp(one['lastSeen']),
                hashrate=float(one['currentHashrate']),
                avg_hashrate={'h24': float(one['averageHashrate'])},
                reported_hashrate=float(one['reportedHashrate']),
                valid_share=int(one['validShares']),
                invalid_share=int(one['invalidShares']),
                stale_share=int(one['staleShares']))
            workers.append(worker)
        self.account.update_workers(workers)

    def __update_account_payments(self):
        url = self.api + '/miner/' + self.wallet_address + '/payouts'
        data = request_data(url)
        payments = []
        for one in data:
            payment = Payment(
                convert_to_eth(float(one['amount'])),
                True,
                datetime.datetime.fromtimestamp(one['paidOn']))
            payments.append(payment)

        self.account.update_payments(payments)

    def __get_profit(self):
        return self.account.get_total_payment() * self.price.get_usd_price()

    def __update_pool_and_price(self):
        url = self.api + '/poolStats'
        data = request_data(url)

        self.hashrate = data['poolStats']['hashRate']
        self.price.update(
            data['price']['usd'],
            data['price']['btc'])

    def __update_network(self):
        url = self.api + '/networkStats'
        data = request_data(url)

        self.hashrate_percent = self.hashrate / float(data['hashrate']) * 100.0

        self.network.update(
            float(data['hashrate']),
            float(data['blockTime']),
            int(data['difficulty']))

    def __str__(self):
        s = bold(cyan(self.name)) + '\n'
        s += bold(cyan('==================')) + '\n'
        s += '\n'
        s += bold(white('Pool:')) + '\n'
        s += '\t' + 'Hashrate: %s (%.2f%%)' % (format_hashrate(self.hashrate), self.hashrate_percent) + '\n'
        s += '\t' + 'Payment Limit: ' + str(self.payment_limit) + '\n'
        s += '\n'
        s += str(self.network) + '\n'
        s += '\n'
        s += str(self.account) + '\n'
        s += '\n'
        s += str(self.price) + '\n'
        s += '\n'
        s += str(self.estimation)
        return s


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
    while True:
        os.system('clear')
        eth()
        time.sleep(30)
        os.system('clear')
        etn()
        time.sleep(30)
        os.system('clear')
        pas()
        time.sleep(30)
