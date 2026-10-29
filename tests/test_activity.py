"""The parts of the activity log and its report that need no database: user agents, addresses, chart geometry."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from activity import network_prefix, parse_user_agent
from activity_report import bars, column_chart, nice_max, period_days

CHROME_WINDOWS = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
EDGE = CHROME_WINDOWS + ' Edg/141.0.0.0'
SAFARI_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                 'Version/18.5 Mobile/15E148 Safari/604.1')
CHROME_ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36'
ANDROID_TABLET = 'Mozilla/5.0 (Linux; Android 13; SM-X200) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
FIREFOX_LINUX = 'Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0'
GOOGLEBOT = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'


@pytest.mark.parametrize('user_agent, expected', [
    (CHROME_WINDOWS, {'device': 'desktop', 'browser': 'Chrome', 'os': 'Windows', 'is_bot': False}),
    (EDGE, {'device': 'desktop', 'browser': 'Edge', 'os': 'Windows', 'is_bot': False}),
    (SAFARI_IPHONE, {'device': 'mobile', 'browser': 'Safari', 'os': 'iOS', 'is_bot': False}),
    (CHROME_ANDROID, {'device': 'mobile', 'browser': 'Chrome', 'os': 'Android', 'is_bot': False}),
    (ANDROID_TABLET, {'device': 'tablet', 'browser': 'Chrome', 'os': 'Android', 'is_bot': False}),
    (FIREFOX_LINUX, {'device': 'desktop', 'browser': 'Firefox', 'os': 'Linux', 'is_bot': False}),
    (GOOGLEBOT, {'device': 'desktop', 'browser': 'Googlebot', 'os': 'Other', 'is_bot': True}),
    ('curl/8.5.0', {'device': 'desktop', 'browser': 'curl', 'os': 'Other', 'is_bot': True}),
    ('', {'device': 'desktop', 'browser': 'Other', 'os': 'Other', 'is_bot': True}),
])
def test_parse_user_agent(user_agent, expected):
    assert parse_user_agent(user_agent) == expected


@pytest.mark.parametrize('address, expected', [
    ('147.32.10.25', '147.32.10.0/24'),
    ('2001:718:2:5::17', '2001:718:2::/48'),
    ('::ffff:192.168.1.7', '192.168.1.0/24'),
    ('', None),
    (None, None),
    ('not an address', None),
])
def test_network_prefix_keeps_only_the_network(address, expected):
    assert network_prefix(address) == expected


@pytest.mark.parametrize('value, expected', [(0, (1, 1)), (1, (1, 1)), (4, (4, 1)), (6, (6, 2)), (10, (10, 5)),
                                             (37, (40, 10)), (1234, (1500, 500))])
def test_nice_max_gives_whole_ticks(value, expected):
    assert nice_max(value) == expected


def test_column_chart_geometry():
    chart = column_chart(['a', 'b', 'c'], [[2], [0], [5]], ['A', 'B', 'C'])
    assert [c['total'] for c in chart['columns']] == [2, 0, 5]
    assert chart['columns'][1]['segments'] == []  # nothing drawn for zero
    assert all(c['w'] <= 24 for c in chart['columns'])  # thin bars, the rest of the band is air
    assert chart['peak']['value'] == 5 and chart['peak']['label'] == 'c'
    assert chart['peak']['top'] > 0  # room above the highest column for its label
    assert [t['label'] for t in chart['ticks']] == ['0', '2', '4', '6']


def test_stacked_column_has_a_gap_and_one_rounded_end():
    chart = column_chart(['m'], [[3, 2]], ['M'])
    first, second = chart['columns'][0]['segments']
    assert first['part'] == 0 and second['part'] == 1
    assert 'Q' not in first['path'] and 'Q' in second['path']  # only the top part has the rounded data end


def test_bars_share_and_percent():
    result = bars([{'label': 'x', 'n': 3}, {'label': 'y', 'n': 1}])
    assert result['total'] == 4
    assert [r['share'] for r in result['rows']] == [1, 1 / 3]
    assert [r['percent'] for r in result['rows']] == [75, 25]
    assert bars([]) == {'rows': [], 'total': 0}


def test_period_days_falls_back_to_the_default():
    assert period_days('7') == 7
    assert period_days('13') == 30
    assert period_days(None) == 30
    assert period_days('x') == 30
