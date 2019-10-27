import unittest
from .base_test_with_data import *
from .test_querysets import SampleModel
from datetime import date, datetime, tzinfo, timedelta
from ipaddress import IPv4Address, IPv6Address
from infi.clickhouse_orm.database import ServerError


class FuncsTestCase(TestCaseWithData):

    def setUp(self):
        super(FuncsTestCase, self).setUp()
        self.database.insert(self._sample_data())

    def _test_qs(self, qs, expected_count):
        logger.info(qs.as_sql())
        count = 0
        for instance in qs:
            count += 1
            logger.info('\t[%d]\t%s' % (count, instance.to_dict()))
        self.assertEqual(count, expected_count)
        self.assertEqual(qs.count(), expected_count)

    def _test_func(self, func, expected_value=None):
        sql = 'SELECT %s AS value' % func.to_sql()
        logger.info(sql)
        result = list(self.database.select(sql))
        logger.info('\t==> %s', result[0].value if result else '<empty>')
        if expected_value is not None:
            self.assertEqual(result[0].value, expected_value)
        return result[0].value if result else None

    def test_func_to_sql(self):
        # No args
        self.assertEqual(F('func').to_sql(), 'func()')
        # String args
        self.assertEqual(F('func', "Wendy's", u"Wendy's").to_sql(), "func('Wendy\\'s', 'Wendy\\'s')")
        # Numeric args
        self.assertEqual(F('func', 1, 1.1, Decimal('3.3')).to_sql(), "func(1, 1.1, 3.3)")
        # Date args
        self.assertEqual(F('func', date(2018, 12, 31)).to_sql(), "func(toDate('2018-12-31'))")
        # Datetime args
        self.assertEqual(F('func', datetime(2018, 12, 31)).to_sql(), "func(toDateTime('1546214400'))")
        # Boolean args
        self.assertEqual(F('func', True, False).to_sql(), "func(1, 0)")
        # Timezone args
        self.assertEqual(F('func', pytz.utc).to_sql(), "func('UTC')")
        self.assertEqual(F('func', pytz.timezone('Europe/Athens')).to_sql(), "func('Europe/Athens')")
        # Null args
        self.assertEqual(F('func', None).to_sql(), "func(NULL)")
        # Fields as args
        self.assertEqual(F('func', SampleModel.color).to_sql(), "func(`color`)")
        # Funcs as args
        self.assertEqual(F('func', F('sqrt', 25)).to_sql(), 'func(sqrt(25))')
        # Iterables as args
        x = [1, 'z', F('foo', 17)]
        for y in [x, tuple(x), iter(x)]:
            self.assertEqual(F('func', y, 5).to_sql(), "func([1, 'z', foo(17)], 5)")
        self.assertEqual(F('func', [(1, 2), (3, 4)]).to_sql(), "func([[1, 2], [3, 4]])")
        # Binary operator functions
        self.assertEqual(F.plus(1, 2).to_sql(), "(1 + 2)")
        self.assertEqual(F.lessOrEquals(1, 2).to_sql(), "(1 <= 2)")

    def test_filter_float_field(self):
        qs = Person.objects_in(self.database)
        # Height > 2
        self._test_qs(qs.filter(F.greater(Person.height, 2)), 0)
        self._test_qs(qs.filter(Person.height > 2), 0)
        # Height > 1.61
        self._test_qs(qs.filter(F.greater(Person.height, 1.61)), 96)
        self._test_qs(qs.filter(Person.height > 1.61), 96)
        # Height < 1.61
        self._test_qs(qs.filter(F.less(Person.height, 1.61)), 4)
        self._test_qs(qs.filter(Person.height < 1.61), 4)

    def test_filter_date_field(self):
        qs = Person.objects_in(self.database)
        # People born on the 30th
        self._test_qs(qs.filter(F('equals', F('toDayOfMonth', Person.birthday), 30)), 3)
        self._test_qs(qs.filter(F('toDayOfMonth', Person.birthday) == 30), 3)
        self._test_qs(qs.filter(F.toDayOfMonth(Person.birthday) == 30), 3)
        # People born on Sunday
        self._test_qs(qs.filter(F('equals', F('toDayOfWeek', Person.birthday), 7)), 18)
        self._test_qs(qs.filter(F('toDayOfWeek', Person.birthday) == 7), 18)
        self._test_qs(qs.filter(F.toDayOfWeek(Person.birthday) == 7), 18)
        # People born on 1976-10-01
        self._test_qs(qs.filter(F('equals', Person.birthday, '1976-10-01')), 1)
        self._test_qs(qs.filter(F('equals', Person.birthday, date(1976, 10, 1))), 1)
        self._test_qs(qs.filter(Person.birthday == date(1976, 10, 1)), 1)

    def test_func_as_field_value(self):
        qs = Person.objects_in(self.database)
        self._test_qs(qs.filter(height__gt=F.plus(1, 0.61)), 96)
        self._test_qs(qs.exclude(birthday=F.today()), 100)
        self._test_qs(qs.filter(birthday__between=['1970-01-01', F.today()]), 100)

    def test_comparison_operators(self):
        one = F.plus(1, 0)
        two = F.plus(1, 1)
        self._test_func(one > one, 0)
        self._test_func(two > one, 1)
        self._test_func(one >= two, 0)
        self._test_func(one >= one, 1)
        self._test_func(one < one, 0)
        self._test_func(one < two, 1)
        self._test_func(two <= one, 0)
        self._test_func(one <= one, 1)
        self._test_func(one == two, 0)
        self._test_func(one == one, 1)
        self._test_func(one != one, 0)
        self._test_func(one != two, 1)

    def test_arithmetic_operators(self):
        one = F.plus(1, 0)
        two = F.plus(1, 1)
        # +
        self._test_func(one + two, 3)
        self._test_func(one + 2, 3)
        self._test_func(2 + one, 3)
        # -
        self._test_func(one - two, -1)
        self._test_func(one - 2, -1)
        self._test_func(1 - two, -1)
        # *
        self._test_func(one * two, 2)
        self._test_func(one * 2, 2)
        self._test_func(1 * two, 2)
        # /
        self._test_func(one / two, 0.5)
        self._test_func(one / 2, 0.5)
        self._test_func(1 / two, 0.5)
        # %
        self._test_func(one % two, 1)
        self._test_func(one % 2, 1)
        self._test_func(1 % two, 1)
        # sign
        self._test_func(-one, -1)
        self._test_func(--one, 1)
        self._test_func(+one, 1)

    def test_logical_operators(self):
        one = F.plus(1, 0)
        two = F.plus(1, 1)
        # &
        self._test_func(one & two, 1)
        self._test_func(one & two, 1)
        self._test_func(one & 0, 0)
        self._test_func(0 & one, 0)
        # |
        self._test_func(one | two, 1)
        self._test_func(one | 0, 1)
        self._test_func(0 | one, 1)
        # ^
        self._test_func(one ^ one, 0)
        #############self._test_func(one ^ 0, 1)
        #############self._test_func(0 ^ one, 1)
        # ~
        self._test_func(~one, 0)
        self._test_func(~~one, 1)
        # compound
        self._test_func(one & 0 | two, 1)
        self._test_func(one & 0 & two, 0)
        self._test_func(one & 0 | 0, 0)
        self._test_func((one | 0) & two, 1)

    def test_date_functions(self):
        d = date(2018, 12, 31)
        dt = datetime(2018, 12, 31, 11, 22, 33)
        self._test_func(F.toYear(d), 2018)
        self._test_func(F.toYear(dt), 2018)
        self._test_func(F.toMonth(d), 12)
        self._test_func(F.toMonth(dt), 12)
        self._test_func(F.toDayOfMonth(d), 31)
        self._test_func(F.toDayOfMonth(dt), 31)
        self._test_func(F.toDayOfWeek(d), 1)
        self._test_func(F.toDayOfWeek(dt), 1)
        self._test_func(F.toHour(dt), 11)
        self._test_func(F.toMinute(dt), 22)
        self._test_func(F.toSecond(dt), 33)
        self._test_func(F.toMonday(d), d)
        self._test_func(F.toMonday(dt), d)
        self._test_func(F.toStartOfMonth(d), date(2018, 12, 1))
        self._test_func(F.toStartOfMonth(dt), date(2018, 12, 1))
        self._test_func(F.toStartOfQuarter(d), date(2018, 10, 1))
        self._test_func(F.toStartOfQuarter(dt), date(2018, 10, 1))
        self._test_func(F.toStartOfYear(d), date(2018, 1, 1))
        self._test_func(F.toStartOfYear(dt), date(2018, 1, 1))
        self._test_func(F.toStartOfMinute(dt), datetime(2018, 12, 31, 11, 22, 0, tzinfo=pytz.utc))
        self._test_func(F.toStartOfFiveMinute(dt), datetime(2018, 12, 31, 11, 20, 0, tzinfo=pytz.utc))
        self._test_func(F.toStartOfFifteenMinutes(dt), datetime(2018, 12, 31, 11, 15, 0, tzinfo=pytz.utc))
        self._test_func(F.toStartOfHour(dt), datetime(2018, 12, 31, 11, 0, 0, tzinfo=pytz.utc))
        self._test_func(F.toStartOfDay(dt), datetime(2018, 12, 31, 0, 0, 0, tzinfo=pytz.utc))
        self._test_func(F.toTime(dt), datetime(1970, 1, 2, 11, 22, 33, tzinfo=pytz.utc))
        self._test_func(F.toTime(dt, pytz.utc), datetime(1970, 1, 2, 11, 22, 33, tzinfo=pytz.utc))
        self._test_func(F.toTime(dt, 'Europe/Athens'), datetime(1970, 1, 2, 13, 22, 33, tzinfo=pytz.utc))
        self._test_func(F.toTime(dt, pytz.timezone('Europe/Athens')), datetime(1970, 1, 2, 13, 22, 33, tzinfo=pytz.utc))
        self._test_func(F.toRelativeYearNum(dt), 2018)
        self._test_func(F.toRelativeYearNum(dt, 'Europe/Athens'), 2018)
        self._test_func(F.toRelativeMonthNum(dt), 2018 * 12 + 12)
        self._test_func(F.toRelativeMonthNum(dt, 'Europe/Athens'), 2018 * 12 + 12)
        self._test_func(F.toRelativeWeekNum(dt), 2557)
        self._test_func(F.toRelativeWeekNum(dt, 'Europe/Athens'), 2557)
        self._test_func(F.toRelativeDayNum(dt), 17896)
        self._test_func(F.toRelativeDayNum(dt, 'Europe/Athens'), 17896)
        self._test_func(F.toRelativeHourNum(dt), 429515)
        self._test_func(F.toRelativeHourNum(dt, 'Europe/Athens'), 429515)
        self._test_func(F.toRelativeMinuteNum(dt), 25770922)
        self._test_func(F.toRelativeMinuteNum(dt, 'Europe/Athens'), 25770922)
        self._test_func(F.toRelativeSecondNum(dt), 1546255353)
        self._test_func(F.toRelativeSecondNum(dt, 'Europe/Athens'), 1546255353)
        self._test_func(F.now(), datetime.utcnow().replace(tzinfo=pytz.utc, microsecond=0))
        self._test_func(F.today(), date.today())
        self._test_func(F.yesterday(), date.today() - timedelta(days=1))
        self._test_func(F.timeSlot(dt), datetime(2018, 12, 31, 11, 0, 0, tzinfo=pytz.utc))
        self._test_func(F.timeSlots(dt, 300), [datetime(2018, 12, 31, 11, 0, 0, tzinfo=pytz.utc)])
        self._test_func(F.formatDateTime(dt, '%D %T'), '12/31/18 11:22:33')
        self._test_func(F.formatDateTime(dt, '%D %T', 'Europe/Athens'), '12/31/18 13:22:33')
        self._test_func(F.addDays(d, 7), date(2019, 1, 7))
        self._test_func(F.addDays(dt, 7, 'Europe/Athens'))
        self._test_func(F.addHours(d, 7), datetime(2018, 12, 31, 7, 0, 0, tzinfo=pytz.utc))
        self._test_func(F.addHours(dt, 7, 'Europe/Athens'))
        self._test_func(F.addMinutes(d, 7), datetime(2018, 12, 31, 0, 7, 0, tzinfo=pytz.utc))
        self._test_func(F.addMinutes(dt, 7, 'Europe/Athens'))
        self._test_func(F.addMonths(d, 7), date(2019, 7, 31))
        self._test_func(F.addMonths(dt, 7, 'Europe/Athens'))
        self._test_func(F.addQuarters(d, 7))
        self._test_func(F.addQuarters(dt, 7, 'Europe/Athens'))
        self._test_func(F.addSeconds(d, 7))
        self._test_func(F.addSeconds(dt, 7, 'Europe/Athens'))
        self._test_func(F.addWeeks(d, 7))
        self._test_func(F.addWeeks(dt, 7, 'Europe/Athens'))
        self._test_func(F.addYears(d, 7))
        self._test_func(F.addYears(dt, 7, 'Europe/Athens'))
        self._test_func(F.subtractDays(d, 3))
        self._test_func(F.subtractDays(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractHours(d, 3))
        self._test_func(F.subtractHours(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractMinutes(d, 3))
        self._test_func(F.subtractMinutes(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractMonths(d, 3))
        self._test_func(F.subtractMonths(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractQuarters(d, 3))
        self._test_func(F.subtractQuarters(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractSeconds(d, 3))
        self._test_func(F.subtractSeconds(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractWeeks(d, 3))
        self._test_func(F.subtractWeeks(dt, 3, 'Europe/Athens'))
        self._test_func(F.subtractYears(d, 3))
        self._test_func(F.subtractYears(dt, 3, 'Europe/Athens'))

    def test_type_conversion_functions(self):
        for f in (F.toUInt8, F.toUInt16, F.toUInt32, F.toUInt64, F.toInt8, F.toInt16, F.toInt32, F.toInt64, F.toFloat32, F.toFloat64):
            self._test_func(f(17), 17)
            self._test_func(f('17'), 17)
        for f in (F.toUInt8OrZero, F.toUInt16OrZero, F.toUInt32OrZero, F.toUInt64OrZero, F.toInt8OrZero, F.toInt16OrZero, F.toInt32OrZero, F.toInt64OrZero, F.toFloat32OrZero, F.toFloat64OrZero):
            self._test_func(f('17'), 17)
            self._test_func(f('a'), 0)
        for f in (F.toDecimal32, F.toDecimal64, F.toDecimal128):
            self._test_func(f(17.17, 2), Decimal('17.17'))
            self._test_func(f('17.17', 2), Decimal('17.17'))
        self._test_func(F.toDate('2018-12-31'), date(2018, 12, 31))
        self._test_func(F.toDateTime('2018-12-31 11:22:33'), datetime(2018, 12, 31, 11, 22, 33, tzinfo=pytz.utc))
        self._test_func(F.toString(123), '123')
        self._test_func(F.toFixedString('123', 5), '123')
        self._test_func(F.toStringCutToZero('123\0'), '123')
        self._test_func(F.CAST(17, 'String'), '17')
        self._test_func(F.parseDateTimeBestEffort('31/12/2019 10:05AM'), datetime(2019, 12, 31, 10, 5, tzinfo=pytz.utc))
        self._test_func(F.parseDateTimeBestEffort('31/12/2019 10:05AM', 'Europe/Athens'))
        with self.assertRaises(ServerError):
            self._test_func(F.parseDateTimeBestEffort('foo'))
        self._test_func(F.parseDateTimeBestEffortOrNull('31/12/2019 10:05AM'), datetime(2019, 12, 31, 10, 5, tzinfo=pytz.utc))
        self._test_func(F.parseDateTimeBestEffortOrNull('31/12/2019 10:05AM', 'Europe/Athens'))
        self._test_func(F.parseDateTimeBestEffortOrNull('foo'), None)
        self._test_func(F.parseDateTimeBestEffortOrZero('31/12/2019 10:05AM'), datetime(2019, 12, 31, 10, 5, tzinfo=pytz.utc))
        self._test_func(F.parseDateTimeBestEffortOrZero('31/12/2019 10:05AM', 'Europe/Athens'))
        self._test_func(F.parseDateTimeBestEffortOrZero('foo'), DateTimeField.class_default)

    def test_string_functions(self):
        self._test_func(F.empty(''), 1)
        self._test_func(F.empty('x'), 0)
        self._test_func(F.notEmpty(''), 0)
        self._test_func(F.notEmpty('x'), 1)
        self._test_func(F.length('x'), 1)
        self._test_func(F.lengthUTF8('x'), 1)
        self._test_func(F.lower('Ab'), 'ab')
        self._test_func(F.upper('Ab'), 'AB')
        self._test_func(F.lowerUTF8('Ab'), 'ab')
        self._test_func(F.upperUTF8('Ab'), 'AB')
        self._test_func(F.reverse('Ab'), 'bA')
        self._test_func(F.reverseUTF8('Ab'), 'bA')
        self._test_func(F.concat('Ab', 'Cd', 'Ef'), 'AbCdEf')
        self._test_func(F.substring('123456', 3, 2), '34')
        self._test_func(F.substringUTF8('123456', 3, 2), '34')
        self._test_func(F.appendTrailingCharIfAbsent('Hello', '!'), 'Hello!')
        self._test_func(F.appendTrailingCharIfAbsent('Hello!', '!'), 'Hello!')
        self._test_func(F.convertCharset(F.convertCharset('Hello', 'latin1', 'utf16'), 'utf16', 'latin1'), 'Hello')

    def test_base64_functions(self):
        try:
            self._test_func(F.base64Decode(F.base64Encode('Hello')), 'Hello')
            self._test_func(F.tryBase64Decode(F.base64Encode('Hello')), 'Hello')
            self._test_func(F.tryBase64Decode('zzz'), None)
        except ServerError as e:
            # ClickHouse version that doesn't support these functions
            raise unittest.SkipTest(e.message)

    def test_replace_functions(self):
        haystack = 'hello'
        self._test_func(F.replace(haystack, 'l', 'L'), 'heLLo')
        self._test_func(F.replaceAll(haystack, 'l', 'L'), 'heLLo')
        self._test_func(F.replaceOne(haystack, 'l', 'L'), 'heLlo')
        self._test_func(F.replaceRegexpAll(haystack, '[eo]', 'X'), 'hXllX')
        self._test_func(F.replaceRegexpOne(haystack, '[eo]', 'X'), 'hXllo')
        self._test_func(F.regexpQuoteMeta('[eo]'), '\\[eo\\]')

    def test_math_functions(self):
        x = 17
        y = 3
        self._test_func(F.e())
        self._test_func(F.pi())
        self._test_func(F.exp(x))
        self._test_func(F.exp10(x))
        self._test_func(F.exp2(x))
        self._test_func(F.log(x))
        self._test_func(F.log10(x))
        self._test_func(F.log2(x))
        self._test_func(F.ln(x))
        self._test_func(F.sqrt(x))
        self._test_func(F.cbrt(x))
        self._test_func(F.erf(x))
        self._test_func(F.erfc(x))
        self._test_func(F.lgamma(x))
        self._test_func(F.tgamma(x))
        self._test_func(F.sin(x))
        self._test_func(F.cos(x))
        self._test_func(F.tan(x))
        self._test_func(F.asin(x))
        self._test_func(F.acos(x))
        self._test_func(F.atan(x))
        self._test_func(F.pow(x, y))
        self._test_func(F.power(x, y))
        self._test_func(F.intExp10(x))
        self._test_func(F.intExp2(x))

    def test_rounding_functions(self):
        x = 22.22222
        n = 3
        self._test_func(F.floor(x), 22)
        self._test_func(F.floor(x, n), 22.222)
        self._test_func(F.ceil(x), 23)
        self._test_func(F.ceil(x, n), 22.223)
        self._test_func(F.ceiling(x), 23)
        self._test_func(F.ceiling(x, n), 22.223)
        self._test_func(F.round(x), 22)
        self._test_func(F.round(x, n), 22.222)
        self._test_func(F.roundAge(x), 18)
        self._test_func(F.roundDown(x, [10, 20, 30]), 20)
        self._test_func(F.roundDuration(x), 10)
        self._test_func(F.roundToExp2(x), 16)

    def test_array_functions(self):
        arr = [1, 2, 3]
        self._test_func(F.emptyArrayDate())
        self._test_func(F.emptyArrayDateTime())
        self._test_func(F.emptyArrayFloat32())
        self._test_func(F.emptyArrayFloat64())
        self._test_func(F.emptyArrayInt16())
        self._test_func(F.emptyArrayInt32())
        self._test_func(F.emptyArrayInt64())
        self._test_func(F.emptyArrayInt8())
        self._test_func(F.emptyArrayString())
        self._test_func(F.emptyArrayToSingle(F.emptyArrayInt16()), [0])
        self._test_func(F.emptyArrayUInt16())
        self._test_func(F.emptyArrayUInt32())
        self._test_func(F.emptyArrayUInt64())
        self._test_func(F.emptyArrayUInt8())
        self._test_func(F.range(7), list(range(7)))
        self._test_func(F.array(*arr), arr)
        self._test_func(F.arrayConcat([1, 2], [3]), arr)
        self._test_func(F.arrayElement([10, 20, 30], 2), 20)
        self._test_func(F.has(arr, 2), 1)
        self._test_func(F.hasAll(arr, [1, 7]), 0)
        self._test_func(F.hasAny(arr, [1, 7]), 1)
        self._test_func(F.indexOf(arr, 3), 3)
        self._test_func(F.countEqual(arr, 2), 1)
        self._test_func(F.arrayEnumerate(arr))
        self._test_func(F.arrayEnumerateDense(arr))
        self._test_func(F.arrayEnumerateDenseRanked(arr))
        self._test_func(F.arrayEnumerateUniq(arr))
        self._test_func(F.arrayEnumerateUniqRanked(arr))
        self._test_func(F.arrayPopBack(arr), [1, 2])
        self._test_func(F.arrayPopFront(arr), [2, 3])
        self._test_func(F.arrayPushBack(arr, 7), arr + [7])
        self._test_func(F.arrayPushFront(arr, 7), [7] + arr)
        self._test_func(F.arrayResize(arr, 5), [1, 2, 3, 0, 0])
        self._test_func(F.arrayResize(arr, 5, 9), [1, 2, 3, 9, 9])
        self._test_func(F.arraySlice(arr, 2), [2, 3])
        self._test_func(F.arraySlice(arr, 2, 1), [2])
        self._test_func(F.arrayUniq(arr + arr), 3)
        self._test_func(F.arrayJoin(arr))
        self._test_func(F.arrayDifference(arr), [0, 1, 1])
        self._test_func(F.arrayDistinct(arr + arr), arr)
        self._test_func(F.arrayIntersect(arr, [3, 4]), [3])
        self._test_func(F.arrayReduce('min', arr), 1)
        self._test_func(F.arrayReverse(arr), [3, 2, 1])

    def test_split_and_merge_functions(self):
        self._test_func(F.splitByChar('_', 'a_b_c'), ['a', 'b', 'c'])
        self._test_func(F.splitByString('__', 'a__b__c'), ['a', 'b', 'c'])
        self._test_func(F.arrayStringConcat(['a', 'b', 'c']), 'abc')
        self._test_func(F.arrayStringConcat(['a', 'b', 'c'], '_'), 'a_b_c')
        self._test_func(F.alphaTokens('aaa.bbb.111'), ['aaa', 'bbb'])

    def test_bit_functions(self):
        x = 17
        y = 4
        z = 5
        self._test_func(F.bitAnd(x, y))
        self._test_func(F.bitNot(x))
        self._test_func(F.bitOr(x, y))
        self._test_func(F.bitRotateLeft(x, y))
        self._test_func(F.bitRotateRight(x, y))
        self._test_func(F.bitShiftLeft(x, y))
        self._test_func(F.bitShiftRight(x, y))
        self._test_func(F.bitTest(x, y))
        self._test_func(F.bitTestAll(x, y))
        self._test_func(F.bitTestAll(x, y, z))
        self._test_func(F.bitTestAny(x, y))
        self._test_func(F.bitTestAny(x, y, z))
        self._test_func(F.bitXor(x, y))

    def test_bitmap_functions(self):
        self._test_func(F.bitmapToArray(F.bitmapBuild([1, 2, 3])), [1, 2, 3])
        self._test_func(F.bitmapContains(F.bitmapBuild([1, 5, 7, 9]), F.toUInt32(9)), 1)
        self._test_func(F.bitmapHasAny(F.bitmapBuild([1,2,3]), F.bitmapBuild([3,4,5])), 1)
        self._test_func(F.bitmapHasAll(F.bitmapBuild([1,2,3]), F.bitmapBuild([3,4,5])), 0)
        self._test_func(F.bitmapToArray(F.bitmapAnd(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5]))), [3])
        self._test_func(F.bitmapToArray(F.bitmapOr(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5]))), [1, 2, 3, 4, 5])
        self._test_func(F.bitmapToArray(F.bitmapXor(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5]))), [1, 2, 4, 5])
        self._test_func(F.bitmapToArray(F.bitmapAndnot(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5]))), [1, 2])
        self._test_func(F.bitmapCardinality(F.bitmapBuild([1, 2, 3, 4, 5])), 5)
        self._test_func(F.bitmapAndCardinality(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5])), 1)
        self._test_func(F.bitmapOrCardinality(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5])), 5)
        self._test_func(F.bitmapXorCardinality(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5])), 4)
        self._test_func(F.bitmapAndnotCardinality(F.bitmapBuild([1, 2, 3]), F.bitmapBuild([3, 4, 5])), 2)

    def test_hash_functions(self):
        args = ['x', 'y', 'z']
        x = 17
        s = 'hello'
        url = 'http://example.com/a/b/c/d'
        self._test_func(F.hex(F.halfMD5(*args)))
        self._test_func(F.hex(F.MD5(s)))
        self._test_func(F.hex(F.sipHash64(*args)))
        self._test_func(F.hex(F.sipHash128(s)))
        self._test_func(F.hex(F.cityHash64(*args)))
        self._test_func(F.hex(F.intHash32(x)))
        self._test_func(F.hex(F.intHash64(x)))
        self._test_func(F.hex(F.SHA1(s)))
        self._test_func(F.hex(F.SHA224(s)))
        self._test_func(F.hex(F.SHA256(s)))
        self._test_func(F.hex(F.URLHash(url)))
        self._test_func(F.hex(F.URLHash(url, 3)))
        self._test_func(F.hex(F.farmHash64(*args)))
        self._test_func(F.javaHash(s))
        self._test_func(F.hiveHash(s))
        self._test_func(F.hex(F.metroHash64(*args)))
        self._test_func(F.jumpConsistentHash(x, 3))
        self._test_func(F.hex(F.murmurHash2_32(*args)))
        self._test_func(F.hex(F.murmurHash2_64(*args)))
        self._test_func(F.hex(F.murmurHash3_32(*args)))
        self._test_func(F.hex(F.murmurHash3_64(*args)))
        self._test_func(F.hex(F.murmurHash3_128(s)))
        self._test_func(F.hex(F.xxHash32(*args)))
        self._test_func(F.hex(F.xxHash64(*args)))

    def test_rand_functions(self):
        self._test_func(F.rand())
        self._test_func(F.rand(17))
        self._test_func(F.rand64())
        self._test_func(F.rand64(17))
        self._test_func(F.randConstant())
        self._test_func(F.randConstant(17))

    def test_encoding_functions(self):
        self._test_func(F.hex(F.unhex('0FA1')), '0FA1')
        self._test_func(F.bitmaskToArray(17))
        self._test_func(F.bitmaskToList(18))

    def test_uuid_functions(self):
        from uuid import UUID
        uuid = self._test_func(F.generateUUIDv4())
        self.assertEqual(type(uuid), UUID)
        s = str(uuid)
        self._test_func(F.toUUID(s), uuid)
        self._test_func(F.UUIDNumToString(F.UUIDStringToNum(s)), s)

    def test_ip_funcs(self):
        self._test_func(F.IPv4NumToString(F.toUInt32(1)), '0.0.0.1')
        self._test_func(F.IPv4NumToStringClassC(F.toUInt32(1)), '0.0.0.xxx')
        self._test_func(F.IPv4StringToNum('0.0.0.17'), 17)
        self._test_func(F.IPv6NumToString(F.IPv4ToIPv6(F.IPv4StringToNum('192.168.0.1'))), '::ffff:192.168.0.1')
        self._test_func(F.IPv6NumToString(F.IPv6StringToNum('2a02:6b8::11')), '2a02:6b8::11')
        self._test_func(F.toIPv4('10.20.30.40'), IPv4Address('10.20.30.40'))
        self._test_func(F.toIPv6('2001:438:ffff::407d:1bc1'), IPv6Address('2001:438:ffff::407d:1bc1'))
        # These require support for tuples:
        # self._test_func(F.IPv4CIDRToRange(F.toIPv4('192.168.5.2'), 16), ['192.168.0.0','192.168.255.255'])
        # self._test_func(F.IPv6CIDRToRange(x, y))
