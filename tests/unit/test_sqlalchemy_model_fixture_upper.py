from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.utils import iteritems
import json
import re

from mock import patch
from unittest import TestCase

from fixtureupper.register import UpperRegister
from tests.unit.models import Article, Author, CoWrite

class BaseTestCase(TestCase):
    def setUp(self):
        self.SqlAlchemyModelFixtureUpper = UpperRegister('SqlAlchemyModel')

        class AuthorFixtureUpper(self.SqlAlchemyModelFixtureUpper):
            model = Author
            defaults = {}

        class ArticleFixtureUpper(self.SqlAlchemyModelFixtureUpper):
            model = Article
            defaults = {}

        class CoWriteFixtureUpper(self.SqlAlchemyModelFixtureUpper):
            model = CoWrite
            defaults = {}

        self.m_fu = self.SqlAlchemyModelFixtureUpper(start_id=150)
        self.AuthorFixtureUpperClass = AuthorFixtureUpper
        self.ArticleFixtureUpperClass = ArticleFixtureUpper
        self.CoWriteFixtureUpperClass = CoWriteFixtureUpper

        self.au_fu = self.m_fu.get_upper('Author')
        self.ar_fu = self.m_fu.get_upper('Article', start_id=250)
        self.co_fu = self.m_fu.get_upper('CoWrite', start_id=370)


class TestSqlAlchemyModelFixtureUpper(BaseTestCase):
    def test_register_fixture_uppers(self):
        self.assertEqual(type(self.m_fu.get_upper('Author')), self.AuthorFixtureUpperClass)
        self.assertEqual(type(self.m_fu.get_upper('Article')), self.ArticleFixtureUpperClass)

    def test_fixups_fixture(self):
        fixture = self.au_fu.fixup(data={})
        self.assertEqual(len(self.au_fu.fixtures), 1)
        self.assertEqual(fixture, self.au_fu.fixtures[0])
        self.assertEqual(fixture.id, 150)
        self.assertIsNone(fixture.name)

    def test_sets_data(self):
        fixture = self.au_fu.fixup(data={
            'name': 'Test Name',
        })
        self.assertEqual(fixture.name, 'Test Name')

    def test_sets_data_with_default(self):
        self.AuthorFixtureUpperClass.defaults['name'] = 'Default Name'
        fixture = self.au_fu.fixup(data={})
        self.assertEqual(fixture.name, 'Default Name')

    def test_sets_data_with_default_function(self):
        self.AuthorFixtureUpperClass.defaults['name'] = lambda self, fixture: 'Author with id %s' % fixture.id

        fixture = self.au_fu.fixup(data={})
        self.assertEqual(fixture.name, 'Author with id 150')

        fixture = self.au_fu.fixup(data={})
        self.assertEqual(fixture.name, 'Author with id 151')

    def test_fixups_multiple_fixtures(self):
        fixtures = self.au_fu.fixup(data=[
            {},
            {'name': 'Test Name 2'},
            {},
        ])
        self.assertEqual(len(self.au_fu.fixtures), 3)
        self.assertEqual(fixtures, self.au_fu.fixtures)

        self.assertIsNone(fixtures[0].name)
        self.assertEqual(fixtures[0].id, 150)

        self.assertEqual(fixtures[1].name, 'Test Name 2')
        self.assertEqual(fixtures[1].id, 151)

        self.assertIsNone(fixtures[2].name)
        self.assertEqual(fixtures[2].id, 152)

    def _assert_relations_and_ids(self, au_fixture, ar_fixture):
        self.assertEqual(au_fixture.articles[0], ar_fixture)
        self.assertEqual(ar_fixture.author, au_fixture)
        self.assertEqual(ar_fixture.main_author_id, au_fixture.id)

    def test_sets_relation_one_way(self):
        au_fixture = self.au_fu.fixup(data={})
        ar_fixture = self.ar_fu.fixup(data={
            'author': au_fixture,
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

    def test_sets_relation_other_way(self):
        ar_fixture = self.ar_fu.fixup(data={})
        au_fixture = self.au_fu.fixup(data={
            'articles': [ar_fixture],
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

    def test_sets_relation_with_generator_function(self):
        au_fixture = self.au_fu.fixup(data={})
        ar_fixture = self.ar_fu.fixup(data={
            'author': lambda self, fixture: au_fixture,
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

    def test_does_not_set_relation_if_None(self):
        au_fixture = self.au_fu.fixup(data={})
        ar_fixture = self.ar_fu.fixup(data={
            'author': None,
        })

        self.assertEqual(len(au_fixture.articles), 0)
        self.assertIsNone(ar_fixture.author)
        self.assertIsNone(ar_fixture.main_author_id)

    def test_does_not_override_relation_if_None(self):
        au_fixture = self.au_fu.fixup(data={})
        ar_fixture = self.ar_fu.fixup(data={
            'author': None,
            'main_author_id': 1,
        })

        self.assertEqual(len(au_fixture.articles), 0)
        self.assertIsNone(ar_fixture.author)
        self.assertEqual(ar_fixture.main_author_id, 1)

    @patch('fixtureupper.model.iteritems')
    def test_sets_relation_with_generator_function_based_on_static_relation(self, mock_iteritems):
        def side_effect(l):
            return sorted(iteritems(l))

        mock_iteritems.side_effect = side_effect

        au_fixture = self.au_fu.fixup(data={
            'co_writes': self.co_fu.fixup(data=[{}])
        })

        ar_fixture = self.ar_fu.fixup(data={
            'author': lambda self, fixture: fixture.co_writes[0].author,
            'co_writes': au_fixture.co_writes,
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

    def test_sets_relation_with_generator_function_in_one_order(self):
        au_fixture = self.au_fu.fixup(data={
            'co_writes': self.co_fu.fixup(data=[{}])
        })

        self.ar_fu.generated_field_order = ['author', 'co_writes']
        ar_fixture = self.ar_fu.fixup(data={
            'author': lambda self, fixture: au_fixture,
            'co_writes': lambda self, fixture: fixture.author.co_writes,
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

        with self.assertRaises(IndexError):
            ar_fixture = self.ar_fu.fixup(data={
                'author': lambda self, fixture: fixture.co_writes[0].author,
                'co_writes': lambda self, fixture: au_fixture.co_writes,
            })

    def test_sets_relation_with_generator_function_in_other_order(self):
        au_fixture = self.au_fu.fixup(data={
            'co_writes': self.co_fu.fixup(data=[{}])
        })

        self.ar_fu.generated_field_order = ['co_writes', 'author']
        ar_fixture = self.ar_fu.fixup(data={
            'author': lambda self, fixture: fixture.co_writes[0].author,
            'co_writes': lambda self, fixture: au_fixture.co_writes,
        })
        self._assert_relations_and_ids(au_fixture, ar_fixture)

        with self.assertRaises(AttributeError):
            ar_fixture = self.ar_fu.fixup(data={
                'author': lambda self, fixture: au_fixture,
                'co_writes': lambda self, fixture: fixture.author.co_writes,
            })


class TestSqlAlchemyModelFixtureUpperReadWrite(BaseTestCase):
    def setUp(self):
        super(TestSqlAlchemyModelFixtureUpperReadWrite, self).setUp()
        self.json_dict = [
            {
                '__class__': 'Article',
                '__value__': {'id': 250, 'main_author_id': 150}
            },
            {
                '__class__': 'Article',
                '__value__': {'id': 251, 'main_author_id': 150}
            },
            {
                '__class__': 'Article',
                '__value__': {'id': 252, 'main_author_id': 151}
            },
            {
                '__class__': 'Author',
                '__value__': {'id': 150}
            },
            {
                '__class__': 'Author',
                '__value__': {'id': 151}
            },
        ]

        ar_fixtures = self.ar_fu.fixup(data=[{}, {}, {}])
        au_fixtures = self.au_fu.fixup(data=[
            {
                'articles': ar_fixtures[:2],
            },
            {
                'articles': ar_fixtures[-1:],
            }
        ])

    def _standardize_white_space(self, s):
        return re.sub(re.compile('^[ ]+', re.MULTILINE), '', s.strip())

    def test_get_current_fixtures_json(self):
        json_dict = json.loads(self.m_fu.get_current_fixtures_json())
        self.assertEqual(json_dict, self.json_dict)

    def test_get_fixtures_json(self):
        json_str = json.dumps(self.json_dict)
        fixtures = self.m_fu.get_fixtures_from_json(json_str)

        self.assertEqual(fixtures[0].id, 250)
        self.assertEqual(fixtures[0].main_author_id, 150)

        self.assertEqual(fixtures[1].id, 251)
        self.assertEqual(fixtures[1].main_author_id, 150)

        self.assertEqual(fixtures[2].id, 252)
        self.assertEqual(fixtures[2].main_author_id, 151)

        self.assertEqual(fixtures[3].id, 150)
        self.assertEqual(fixtures[4].id, 151)

    def test_get_fixtures_json_in_different_order(self):
        self.SqlAlchemyModelFixtureUpper.all_fixtures_order = ['Author', 'Article']
        json_dict = json.loads(self.m_fu.get_current_fixtures_json())
        expected_json_dict = self.json_dict[3:] + self.json_dict[:3]
        self.assertEqual(json_dict, expected_json_dict)

    def test_writes_as_sql(self):
        query = self.m_fu.stats_fixtures_to_sql(self.m_fu.get_all_fixtures())
        self.assertEqual(
            self._standardize_white_space(query),
            self._standardize_white_space("""
                INSERT INTO article (id, main_author_id) VALUES
                (250, 150),
                (251, 150),
                (252, 151);

                INSERT INTO author (id) VALUES
                (150),
                (151);
            """)
        )

    def test_writes_as_sql_in_different_order(self):
        self.SqlAlchemyModelFixtureUpper.all_fixtures_order = ['Author', 'Article']
        query = self.m_fu.stats_fixtures_to_sql(self.m_fu.get_all_fixtures())
        self.assertEqual(
            self._standardize_white_space(query),
            self._standardize_white_space("""
                INSERT INTO author (id) VALUES
                (150),
                (151);

                INSERT INTO article (id, main_author_id) VALUES
                (250, 150),
                (251, 150),
                (252, 151);
            """)
        )