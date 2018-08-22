# -*- coding: utf-8 -*-
import datetime
import re

import pytest
import six
from six.moves import StringIO

from xunit2testrail.testrail.client import Case

if six.PY2:
    import mock
else:
    from unittest import mock


@pytest.fixture
def xunit_case():
    from xunit2testrail.vendor.xunitparser import TestCase as XunitCase
    xunit_case = XunitCase(classname='a.TestClass', methodname='test_method')
    xunit_case.result = 'success'
    xunit_case.time = datetime.timedelta(seconds=1)
    return xunit_case


@pytest.fixture
def xunit_case_skipped(xunit_case):
    xunit_case.result = 'skipped'
    return xunit_case


@pytest.fixture
def paste_api(api_mock):
    paste_url = re.escape('http://example.com/json/?method=pastes.newPaste')
    api_mock.register_uri(
        'POST', re.compile(paste_url), json={"data": "123"}, complete_qs=True)


def test_parse_report(reporter):
    suite, result = reporter.get_xunit_test_suite()
    assert all(suite)
    assert len(list(suite)) == 65
    assert len(result.skipped) == 25
    assert len(result.failures) == 13


def test_print_run_url(reporter, mocker):
    stdout = mocker.patch('sys.stdout', new=StringIO())
    reporter.print_run_url(mock.Mock(url='http://report_url/'))
    assert stdout.getvalue() == ('[TestRun URL] http://report_url/\n')


@pytest.mark.parametrize('classname, methodname, expected_url', (
    ('a.b.c.TClass', 'test_method[2](1)',
     'http://t_job/testReport/a.b.c/TClass/test_method_2__1_/'),
    ('a.b.c.TClass', 'test_method[id-1]',
     'http://t_job/testReport/a.b.c/TClass/test_method_id_1_/'),
    ('a.b.c.TClass', 'test_method[a,b]',
     'http://t_job/testReport/a.b.c/TClass/test_method_a_b_/'),
    ('TClass', 'test_method[a,b]',
     'http://t_job/testReport/(root)/TClass/test_method_a_b_/'),
    ('TClass', 'test_method[AS,b]',
     'http://t_job/testReport/(root)/TClass/test_method_AS_b_/'), ))
def test_get_jenkins_report_url(reporter, classname, methodname, expected_url):

    from xunit2testrail.vendor.xunitparser import TestCase as XunitCase
    xunit_case = XunitCase(classname=classname, methodname=methodname)
    reporter.test_results_link = 'http://t_job/'
    assert expected_url == reporter.get_jenkins_report_url(xunit_case)


def test_add_result_to_case(reporter, xunit_case):
    testrail_case = Case()
    xunit_case.message = u'успешно'
    xunit_case.stderr = u'stderr message сообщение'
    xunit_case.stdout = u'stdout message сообщение'
    xunit_case.trace = u'trace сообщение'
    report_url = reporter.get_jenkins_report_url(xunit_case)
    reporter.add_result_to_case(testrail_case, xunit_case)
    comment = testrail_case.result.comment
    assert report_url in comment
    assert reporter.env_description in comment
    assert xunit_case.message in comment
    assert xunit_case.stderr not in comment
    assert xunit_case.stdout not in comment
    assert xunit_case.trace in comment


@pytest.mark.parametrize('send_skipped', [True, False])
def test_send_skipped_param(reporter, xunit_case_skipped, send_skipped):
    reporter.send_skipped = send_skipped
    testrail_case = Case()
    reporter.add_result_to_case(testrail_case, xunit_case_skipped)
    assert send_skipped == (testrail_case.result is not None)


def test_no_trace_on_success_test_on_testrail(reporter, xunit_case):
    assert 'trace' not in reporter.gen_testrail_comment(xunit_case)


def test_paste_result_link(reporter, xunit_case, paste_api):
    link = reporter.save_to_paste(xunit_case)
    assert link == "http://example.com/show/123/"


@pytest.mark.parametrize('prop, value', (
    ('trace', "i'm trace"),
    ('stdout', "i'm stdout"),
    ('stderr', "i'm stderr"), ))
def test_paste_store_data(api_mock, reporter, xunit_case, paste_api, prop,
                          value):
    absent_props = ['trace', 'stdout', 'stderr']
    absent_props.remove(prop)
    setattr(xunit_case, prop, value)
    reporter.save_to_paste(xunit_case)
    payload = api_mock.request_history[-1].json()
    assert value in payload['code']
    for absent_prop in absent_props:
        assert absent_prop not in payload['code']
