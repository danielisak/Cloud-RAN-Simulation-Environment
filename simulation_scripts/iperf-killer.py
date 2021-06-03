import subprocess

ps_list = subprocess.check_output(
    'ps -ax|grep iperf3', shell=True).decode('utf-8').strip().split('\n')
kill_list = list(filter(lambda a: 'iperf3 -s' in a, ps_list))
kill_list = list(map(lambda a: a.split()[0], kill_list))

for pid in kill_list:
    subprocess.call('kill -2 ' + pid, shell=True)
    print(subprocess.check_output('ps -ax|grep iperf3',
          shell=True).decode('utf-8').strip().split('\n'))
