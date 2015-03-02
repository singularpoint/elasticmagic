from mock import MagicMock

from elasticmagic import agg, Document, DynamicDocument, Field, SearchQuery, Term, Match, Index
from elasticmagic.types import Integer, Float
from elasticmagic.ext.queryfilter import QueryFilter, FacetFilter, RangeFilter
from elasticmagic.ext.queryfilter import FacetQueryFilter, FacetQueryValue
from elasticmagic.ext.queryfilter import OrderingFilter, OrderingValue
from elasticmagic.ext.queryfilter import PageFilter

from .base import BaseTestCase


class CarType(object):
    def __init__(self, id, title):
        self.id = id
        self.title = title

TYPES = {
    t.id: t
    for t in [
            CarType(0, 'Sedan'),
            CarType(1, 'Station Wagon'),
            CarType(2, 'Hatchback'),
            CarType(3, 'Coupe'),
    ]
}

def type_mapper(values):
    return TYPES


class QueryFilterTest(BaseTestCase):
    def test_facet_filter(self):
        class CarQueryFilter(QueryFilter):
            type = FacetFilter(self.index.car.type, instance_mapper=type_mapper, type=Integer)
            vendor = FacetFilter(self.index.car.vendor, aggs={'min_price': agg.Min(self.index.car.price)})
            model = FacetFilter(self.index.car.model)

        qf = CarQueryFilter()

        sq = self.index.query()
        sq = qf.apply(sq, {})
        self.assert_expression(
            sq,
            {
                "aggregations": {
                    "qf.type": {
                        "terms": {"field": "type"}
                    },
                    "qf.vendor": {
                        "terms": {"field": "vendor"},
                        "aggregations": {
                            "min_price": {
                                "min": {"field": "price"}
                            }
                        }
                    },
                    "qf.model": {
                        "terms": {"field": "model"}
                    }
                }
            }
        )
        
        sq = (
            self.index.query(Match(self.index.car.name, 'test'))
            .filter(self.index.car.status == 0)
            .post_filter(self.index.car.date_created > 'now-1y',
                         meta={'tags': {qf.get_name()}})
        )
        sq = qf.apply(sq, {'type': ['0', '1:break', '3', 'null'], 'vendor': ['Subaru']})
        self.assert_expression(
            sq,
            {
                "query": {
                    "filtered": {
                        "query": {
                            "match": {"name": "test"}
                        },
                        "filter": {
                            "term": {"status": 0}
                        }
                    }
                },
                "aggregations": {
                    "qf.type.filter": {
                        "filter": {
                            "term": {"vendor": "Subaru"}
                        },
                        "aggregations": {
                            "qf.type": {
                                "terms": {"field": "type"}
                            }
                        }
                    },
                    "qf.vendor.filter": {
                        "filter": {
                            "terms": {"type": [0, 1, 3]}
                        },
                        "aggregations": {
                            "qf.vendor": {
                                "terms": {"field": "vendor"},
                                "aggregations": {
                                    "min_price": {
                                        "min": {"field": "price"}
                                    }
                                }
                            }
                        }
                    },
                    "qf.model.filter": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"terms": {"type": [0, 1, 3]}},
                                    {"term": {"vendor": "Subaru"}}
                                ]
                            }
                        },
                        "aggregations": {
                            "qf.model": {
                                "terms": {"field": "model"}
                            }
                        }
                    }
                },
                "post_filter": {
                    "bool": {
                        "must": [
                            {"range": {"date_created": {"gt": "now-1y"}}},
                            {"terms": {"type": [0, 1, 3]}},
                            {"term": {"vendor": "Subaru"}}
                        ]
                    }
                }
            }
        )

        self.client.search = MagicMock(
           return_value={
                "hits": {
                    "hits": [],
                    "max_score": 1.829381,
                    "total": 893
                },
                "aggregations": {
                    "qf.type.filter": {
                        "doc_count": 1298,
                        "qf.type": {
                            "buckets": [
                                {
                                    "key": 0,
                                    "doc_count": 744
                                },
                                {
                                    "key": 2,
                                    "doc_count": 392
                                },
                                {
                                    "key": 1,
                                    "doc_count": 162
                                }
                            ]
                        }
                    },
                    "qf.vendor.filter": {
                        "doc_count": 2153,
                        "qf.vendor": {
                            "buckets": [
                                {
                                    "key": "Subaru",
                                    "doc_count": 2153,
                                    "min_price": {"value": 4000}
                                        ,
                                },
                            ]
                        }
                    },
                    "qf.model.filter": {
                        "doc_count": 2153,
                        "qf.model": {
                            "buckets": [
                                {
                                    "key": "Imprezza",
                                    "doc_count": 1586
                                },
                                {
                                    "key": "Forester",
                                    "doc_count": 456
                                },
                            ]
                        }
                    }
                }
            }
        )

        qf.process_results(sq.result)

        type_filter = qf.type
        self.assertEqual(len(type_filter.selected_values), 3)
        self.assertEqual(len(type_filter.values), 1)
        self.assertEqual(len(type_filter.all_values), 4)
        self.assertEqual(type_filter.all_values[0].value, 0)
        self.assertEqual(type_filter.all_values[0].count, 744)
        self.assertEqual(type_filter.all_values[0].count_text, '744')
        self.assertEqual(type_filter.all_values[0].selected, True)
        self.assertEqual(type_filter.all_values[0].instance.title, 'Sedan')
        self.assertIs(type_filter.all_values[0], type_filter.get_value(0))
        self.assertIs(type_filter.all_values[0], type_filter.selected_values[0])
        self.assertEqual(type_filter.all_values[1].value, 2)
        self.assertEqual(type_filter.all_values[1].count, 392)
        self.assertEqual(type_filter.all_values[1].count_text, '+392')
        self.assertEqual(type_filter.all_values[1].selected, False)
        self.assertEqual(type_filter.all_values[1].instance.title, 'Hatchback')
        self.assertIs(type_filter.all_values[1], type_filter.get_value(2))
        self.assertIs(type_filter.all_values[1], type_filter.values[0])
        self.assertEqual(type_filter.all_values[2].value, 1)
        self.assertEqual(type_filter.all_values[2].count, 162)
        self.assertEqual(type_filter.all_values[2].count_text, '162')
        self.assertEqual(type_filter.all_values[2].selected, True)
        self.assertEqual(type_filter.all_values[2].instance.title, 'Station Wagon')
        self.assertIs(type_filter.all_values[2], type_filter.get_value(1))
        self.assertIs(type_filter.all_values[2], type_filter.selected_values[1])
        self.assertEqual(type_filter.all_values[3].value, 3)
        self.assertIs(type_filter.all_values[3].count, None)
        self.assertEqual(type_filter.all_values[3].count_text, '')
        self.assertEqual(type_filter.all_values[3].selected, True)
        self.assertEqual(type_filter.all_values[3].instance.title, 'Coupe')
        self.assertIs(type_filter.all_values[3], type_filter.get_value(3))
        self.assertIs(type_filter.all_values[3], type_filter.selected_values[2])
        vendor_filter = qf.vendor
        self.assertEqual(len(vendor_filter.selected_values), 1)
        self.assertEqual(len(vendor_filter.values), 0)
        self.assertEqual(len(vendor_filter.all_values), 1)
        self.assertEqual(vendor_filter.all_values[0].value, 'Subaru')
        self.assertEqual(vendor_filter.all_values[0].count, 2153)
        self.assertEqual(vendor_filter.all_values[0].count_text, '2153')
        self.assertEqual(vendor_filter.all_values[0].selected, True)
        self.assertEqual(vendor_filter.all_values[0].bucket.get_aggregation('min_price').value, 4000)
        self.assertIs(vendor_filter.all_values[0], vendor_filter.selected_values[0])
        self.assertIs(vendor_filter.all_values[0], vendor_filter.get_value('Subaru'))
        model_filter = qf.model
        self.assertEqual(len(model_filter.selected_values), 0)
        self.assertEqual(len(model_filter.values), 2)
        self.assertEqual(len(model_filter.all_values), 2)
        self.assertEqual(model_filter.all_values[0].value, 'Imprezza')
        self.assertEqual(model_filter.all_values[0].count, 1586)
        self.assertEqual(model_filter.all_values[0].count_text, '1586')
        self.assertEqual(model_filter.all_values[0].selected, False)
        self.assertIs(model_filter.all_values[0], model_filter.values[0])
        self.assertIs(model_filter.all_values[0], model_filter.get_value('Imprezza'))
        self.assertEqual(model_filter.all_values[1].value, 'Forester')
        self.assertEqual(model_filter.all_values[1].count, 456)
        self.assertEqual(model_filter.all_values[1].count_text, '456')
        self.assertEqual(model_filter.all_values[1].selected, False)
        self.assertIs(model_filter.all_values[1], model_filter.values[1])
        self.assertIs(model_filter.all_values[1], model_filter.get_value('Forester'))

    def test_range_filter(self):
        class CarDocument(Document):
            __doc_type__ = 'car'

            price = Field(Integer)
            engine_displacement = Field(Float)

        class CarQueryFilter(QueryFilter):
            price = RangeFilter(CarDocument.price, compute_min_max=False)
            disp = RangeFilter(CarDocument.engine_displacement, compute_enabled=False)

        qf = CarQueryFilter()

        sq = self.index.query()
        sq = qf.apply(sq, {'price__lte': ['10000']})
        self.assert_expression(
            sq,
            {
                "aggregations": {
                    "qf.price.enabled": {"filter": {"exists": {"field": "price"}}},
                    "qf.disp.filter": {
                        "filter": {
                            "range": {"price": {"lte": 10000}}
                        },
                        "aggregations": {
                            "qf.disp.min": {"min": {"field": "engine_displacement"}},
                            "qf.disp.max": {"max": {"field": "engine_displacement"}}
                        }
                    }
                },
                "post_filter": {
                    "range": {"price": {"lte": 10000}}
                }
            }
        )

        self.client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [],
                    "max_score": 1.829381,
                    "total": 893
                },
                "aggregations": {
                    "qf.price.enabled": {"doc_count": 890},
                    "qf.disp.filter": {
                        "doc_count": 237,
                        "qf.disp.min": {"value": 1.6},
                        "qf.disp.max": {"value": 3.0}
                    }
                }
            }
        )
        qf.process_results(sq.result)

        price_filter = qf.price
        self.assertEqual(price_filter.enabled, True)
        self.assertIs(price_filter.min, None)
        self.assertIs(price_filter.max, None)
        self.assertIs(price_filter.from_value, None)
        self.assertEqual(price_filter.to_value, 10000)
        disp_filter = qf.disp
        self.assertIs(disp_filter.enabled, None)
        self.assertAlmostEqual(disp_filter.min, 1.6)
        self.assertAlmostEqual(disp_filter.max, 3.0)
        self.assertIs(disp_filter.from_value, None)
        self.assertIs(disp_filter.to_value, None)

    def test_range_filter_dynamic_document(self):
        class CarQueryFilter(QueryFilter):
            price = RangeFilter(self.index.car.price, type=Integer)
            disp = RangeFilter(self.index.car.engine_displacement, type=Float)

        qf = CarQueryFilter()

        sq = self.index.query()
        sq = qf.apply(sq, {'price__lte': ['10000']})
        self.assert_expression(
            sq,
            {
                "aggregations": {
                    "qf.price.enabled": {"filter": {"exists": {"field": "price"}}},
                    "qf.price.min": {"min": {"field": "price"}},
                    "qf.price.max": {"max": {"field": "price"}},
                    "qf.disp.enabled": {"filter": {"exists": {"field": "engine_displacement"}}},
                    "qf.disp.filter": {
                        "filter": {
                            "range": {"price": {"lte": 10000}}
                        },
                        "aggregations": {
                            "qf.disp.min": {"min": {"field": "engine_displacement"}},
                            "qf.disp.max": {"max": {"field": "engine_displacement"}}
                        }
                    }
                },
                "post_filter": {
                    "range": {"price": {"lte": 10000}}
                }
            }
        )

        self.client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [],
                    "max_score": 1.829381,
                    "total": 893
                },
                "aggregations": {
                    "qf.price.enabled": {"doc_count": 890},
                    "qf.price.min": {"value": 7500},
                    "qf.price.max": {"value": 25800},
                    "qf.disp.enabled": {"doc_count": 888},
                    "qf.disp.filter": {
                        "doc_count": 237,
                        "qf.disp.min": {"value": 1.6},
                        "qf.disp.max": {"value": 3.0}
                    }
                }
            }
        )
        qf.process_results(sq.result)

        price_filter = qf.price
        self.assertEqual(price_filter.enabled, True)
        self.assertEqual(price_filter.min, 7500)
        self.assertEqual(price_filter.max, 25800)
        self.assertIs(price_filter.from_value, None)
        self.assertEqual(price_filter.to_value, 10000)
        disp_filter = qf.disp
        self.assertAlmostEqual(disp_filter.enabled, True)
        self.assertAlmostEqual(disp_filter.min, 1.6)
        self.assertAlmostEqual(disp_filter.max, 3.0)
        self.assertIs(disp_filter.from_value, None)
        self.assertIs(disp_filter.to_value, None)
        
    def test_facet_query_filter(self):
        class CarQueryFilter(QueryFilter):
            is_new = FacetQueryFilter(
                FacetQueryValue('true', self.index.car.state == 'new')
            )
            price = FacetQueryFilter(
                FacetQueryValue('*-10000', self.index.car.price <= 10000),
                FacetQueryValue('10000-20000', self.index.car.price.range(gt=10000, lte=20000)),
                FacetQueryValue('20000-30000', self.index.car.price.range(gt=20000, lte=30000)),
                FacetQueryValue('30000-*', self.index.car.price.range(gt=30000)),
                aggs={'disp_avg': agg.Avg(self.index.car.engine_displacement)}
            )

        qf = CarQueryFilter()

        sq = self.index.query()
        sq = qf.apply(sq, {'is_new': ['true', 'false']})
        self.assert_expression(
            sq,
            {
                "aggregations": {
                    "qf.is_new:true": {
                        "filter": {
                            "term": {"state": "new"}
                        }
                    },
                    "qf.price.filter": {
                        "filter": {
                            "term": {"state": "new"}
                        },
                        "aggregations": {
                            "qf.price:*-10000": {
                                "filter": {
                                    "range": {"price": {"lte": 10000}}
                                },
                                "aggregations": {
                                    "disp_avg": {
                                        "avg": {"field": "engine_displacement"}
                                    }
                                }
                            },
                            "qf.price:10000-20000": {
                                "filter": {
                                    "range": {"price": {"gt": 10000, "lte": 20000}}
                                },
                                "aggregations": {
                                    "disp_avg": {
                                        "avg": {"field": "engine_displacement"}
                                    }
                                }
                            },
                            "qf.price:20000-30000": {
                                "filter": {
                                    "range": {"price": {"gt": 20000, "lte": 30000}}
                                },
                                "aggregations": {
                                    "disp_avg": {
                                        "avg": {"field": "engine_displacement"}
                                    }
                                }
                            },
                            "qf.price:30000-*": {
                                "filter": {
                                    "range": {"price": {"gt": 30000}}
                                },
                                "aggregations": {
                                    "disp_avg": {
                                        "avg": {"field": "engine_displacement"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post_filter": {
                    "term": {"state": "new"}
                }
            }
        )

        self.client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [],
                    "max_score": 1.829381,
                    "total": 893
                },
                "aggregations": {
                    "qf.is_new:true": {
                        "doc_count": 82
                    },
                    "qf.price.filter": {
                        "doc_count": 82,
                        "qf.price:*-10000": {
                            "doc_count": 11,
                            "disp_avg": {"value": 1.56}
                        },
                        "qf.price:10000-20000": {
                            "doc_count": 16,
                            "disp_avg": {"value": 2.4}
                        },
                        "qf.price:20000-30000": {
                            "doc_count": 23,
                            "disp_avg": {"value": 2.85}
                        },
                        "qf.price:30000-*": {
                            "doc_count": 32,
                            "disp_avg": {"value": 2.92}
                        }
                    }
                }
            }
        )
        qf.process_results(sq.result)
        self.assertEqual(len(qf.is_new.all_values), 1)
        self.assertEqual(len(qf.is_new.selected_values), 1)
        self.assertEqual(len(qf.is_new.values), 0)
        self.assertEqual(qf.is_new.get_value('true').value, 'true')
        self.assertEqual(qf.is_new.get_value('true').count, 82)
        self.assertEqual(qf.is_new.get_value('true').count_text, '82')
        self.assertEqual(qf.is_new.get_value('true').selected, True)
        self.assertEqual(len(qf.price.all_values), 4)
        self.assertEqual(len(qf.price.selected_values), 0)
        self.assertEqual(len(qf.price.values), 4)
        self.assertEqual(qf.price.get_value('*-10000').value, '*-10000')
        self.assertEqual(qf.price.get_value('*-10000').count, 11)
        self.assertEqual(qf.price.get_value('*-10000').count_text, '11')
        self.assertEqual(qf.price.get_value('*-10000').selected, False)
        self.assertEqual(qf.price.get_value('*-10000').agg.get_aggregation('disp_avg').value, 1.56)
        self.assertEqual(qf.price.get_value('10000-20000').value, '10000-20000')
        self.assertEqual(qf.price.get_value('10000-20000').count, 16)
        self.assertEqual(qf.price.get_value('10000-20000').count_text, '16')
        self.assertEqual(qf.price.get_value('10000-20000').selected, False)
        self.assertEqual(qf.price.get_value('10000-20000').agg.get_aggregation('disp_avg').value, 2.4)
        self.assertEqual(qf.price.get_value('20000-30000').value, '20000-30000')
        self.assertEqual(qf.price.get_value('20000-30000').count, 23)
        self.assertEqual(qf.price.get_value('20000-30000').count_text, '23')
        self.assertEqual(qf.price.get_value('20000-30000').selected, False)
        self.assertEqual(qf.price.get_value('20000-30000').agg.get_aggregation('disp_avg').value, 2.85)
        self.assertEqual(qf.price.get_value('30000-*').value, '30000-*')
        self.assertEqual(qf.price.get_value('30000-*').count, 32)
        self.assertEqual(qf.price.get_value('30000-*').count_text, '32')
        self.assertEqual(qf.price.get_value('30000-*').selected, False)
        self.assertEqual(qf.price.get_value('30000-*').agg.get_aggregation('disp_avg').value, 2.92)

        qf = CarQueryFilter()
        sq = self.index.query(self.index.car.year == 2014)
        sq = qf.apply(sq, {'price': ['*-10000', '10000-20000', 'null']})
        self.assert_expression(
            sq,
            {
                "query": {
                    "term": {"year": 2014}
                },
                "aggregations": {
                    "qf.is_new.filter": {
                        "filter": {
                            "bool": {
                                "should": [
                                    {
                                        "range": {
                                            "price": {"lte": 10000}
                                        }
                                    },
                                    {
                                        "range": {
                                            "price": {"gt": 10000, "lte": 20000}
                                        }
                                    }
                                ]
                            }
                        },
                        "aggregations": {
                            "qf.is_new:true": {
                                "filter": {
                                    "term": {"state": "new"}
                                }
                            }
                        }
                    },
                    "qf.price:*-10000": {
                        "filter": {
                            "range": {"price": {"lte": 10000}}
                        },
                        "aggregations": {
                            "disp_avg": {
                                "avg": {"field": "engine_displacement"}
                            }
                        }
                    },
                    "qf.price:10000-20000": {
                        "filter": {
                            "range": {"price": {"gt": 10000, "lte": 20000}}
                        },
                        "aggregations": {
                            "disp_avg": {
                                "avg": {"field": "engine_displacement"}
                            }
                        }
                    },
                    "qf.price:20000-30000": {
                        "filter": {
                            "range": {"price": {"gt": 20000, "lte": 30000}}
                        },
                        "aggregations": {
                            "disp_avg": {
                                "avg": {"field": "engine_displacement"}
                            }
                        }
                    },
                    "qf.price:30000-*": {
                        "filter": {
                            "range": {"price": {"gt": 30000}}
                        },
                        "aggregations": {
                            "disp_avg": {
                                "avg": {"field": "engine_displacement"}
                            }
                        }
                    }
                },
                "post_filter": {
                    "bool": {
                        "should": [
                            {
                                "range": {
                                    "price": {"lte": 10000}
                                }
                            },
                            {
                                "range": {
                                    "price": {"gt": 10000, "lte": 20000}
                                }
                            }
                        ]
                    }
                }
            }
        )

        self.client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [],
                    "max_score": 1.0,
                    "total": 514
                },
                "aggregations": {
                    "qf.is_new.filter": {
                        "doc_count": 34,
                        "qf.is_new:true": {
                            "doc_count": 32
                        }
                    },
                    "qf.price:*-10000": {
                        "doc_count": 7,
                        "disp_avg": {"value": 1.43}
                    },
                    "qf.price:10000-20000": {
                        "doc_count": 11,
                        "disp_avg": {"value": 1.98}
                    },
                    "qf.price:20000-30000": {
                        "doc_count": 6,
                        "disp_avg": {"value": 2.14}
                    },
                    "qf.price:30000-*": {
                        "doc_count": 10,
                        "disp_avg": {"value": 2.67}
                    }
                }
            }
        )
        qf.process_results(sq.result)
        self.assertEqual(len(qf.is_new.all_values), 1)
        self.assertEqual(len(qf.is_new.selected_values), 0)
        self.assertEqual(len(qf.is_new.values), 1)
        self.assertEqual(qf.is_new.get_value('true').value, 'true')
        self.assertEqual(qf.is_new.get_value('true').count, 32)
        self.assertEqual(qf.is_new.get_value('true').count_text, '32')
        self.assertEqual(qf.is_new.get_value('true').selected, False)
        self.assertEqual(len(qf.price.all_values), 4)
        self.assertEqual(len(qf.price.selected_values), 2)
        self.assertEqual(len(qf.price.values), 2)
        self.assertEqual(qf.price.get_value('*-10000').value, '*-10000')
        self.assertEqual(qf.price.get_value('*-10000').count, 7)
        self.assertEqual(qf.price.get_value('*-10000').count_text, '7')
        self.assertEqual(qf.price.get_value('*-10000').selected, True)
        self.assertEqual(qf.price.get_value('*-10000').agg.get_aggregation('disp_avg').value, 1.43)
        self.assertEqual(qf.price.get_value('10000-20000').value, '10000-20000')
        self.assertEqual(qf.price.get_value('10000-20000').count, 11)
        self.assertEqual(qf.price.get_value('10000-20000').count_text, '11')
        self.assertEqual(qf.price.get_value('10000-20000').selected, True)
        self.assertEqual(qf.price.get_value('10000-20000').agg.get_aggregation('disp_avg').value, 1.98)
        self.assertEqual(qf.price.get_value('20000-30000').value, '20000-30000')
        self.assertEqual(qf.price.get_value('20000-30000').count, 6)
        self.assertEqual(qf.price.get_value('20000-30000').count_text, '+6')
        self.assertEqual(qf.price.get_value('20000-30000').selected, False)
        self.assertEqual(qf.price.get_value('20000-30000').agg.get_aggregation('disp_avg').value, 2.14)
        self.assertEqual(qf.price.get_value('30000-*').value, '30000-*')
        self.assertEqual(qf.price.get_value('30000-*').count, 10)
        self.assertEqual(qf.price.get_value('30000-*').count_text, '+10')
        self.assertEqual(qf.price.get_value('30000-*').selected, False)
        self.assertEqual(qf.price.get_value('30000-*').agg.get_aggregation('disp_avg').value, 2.67)

    def test_ordering(self):
        class CarQueryFilter(QueryFilter):
            sort = OrderingFilter(
                OrderingValue(
                    'popularity',
                    [self.index.car.popularity.desc(),
                     self.index.car.opinion_count.desc(missing='_last')],
                ),
                OrderingValue('price', [self.index.car.price]),
                OrderingValue('-price', [self.index.car.price.desc()]),
                default='popularity',
            )

        sq = self.index.query()

        qf = CarQueryFilter()
        self.assert_expression(
            qf.apply(sq, {}),
            {
                "sort": [
                    {
                        "popularity": "desc"
                    },
                    {
                        "opinion_count": {"order": "desc", "missing": "_last"}
                    }
                ]
            }
        )

        self.assertEqual(qf.sort.selected_value.value, 'popularity')
        self.assertEqual(qf.sort.selected_value.selected, True)
        self.assertEqual(qf.sort.get_value('price').selected, False)
        self.assertEqual(qf.sort.get_value('-price').selected, False)

        qf = CarQueryFilter()
        self.assert_expression(
            qf.apply(sq, {'sort': ['price']}),
            {
                "sort": [
                    "price"
                ]
            }
        )
        self.assertEqual(qf.sort.selected_value.value, 'price')
        self.assertEqual(qf.sort.selected_value.selected, True)
        self.assertEqual(qf.sort.get_value('popularity').selected, False)
        self.assertEqual(qf.sort.get_value('-price').selected, False)

    def test_page(self):
        class CarQueryFilter(QueryFilter):
            page = PageFilter(per_page_values=[10, 25, 50])

        sq = self.index.search_query()

        qf = CarQueryFilter()
        self.assert_expression(
            qf.apply(sq, {}),
            {
                "size": 10
            }
        )

        self.assert_expression(
            qf.apply(sq, {'page': 3}),
            {
                "size": 10,
                "from": 20
            }
        )

        self.assert_expression(
            qf.apply(sq, {'per_page': 25}),
            {
                "size": 25
            }
        )

        self.assert_expression(
            qf.apply(sq, {'page': 3, 'per_page': 100}),
            {
                "size": 10,
                "from": 20
            }
        )

        self.client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [
                        {"_id": "21", "_type": "car"},
                        {"_id": "22", "_type": "car"},
                        {"_id": "23", "_type": "car"},
                        {"_id": "24", "_type": "car"},
                        {"_id": "25", "_type": "car"},
                        {"_id": "26", "_type": "car"},
                        {"_id": "27", "_type": "car"},
                        {"_id": "28", "_type": "car"},
                        {"_id": "29", "_type": "car"},
                        {"_id": "30", "_type": "car"},
                    ],
                    "max_score": 5.487631,
                    "total": 105
                }
            }
        )
        qf.process_results(sq.result)
        self.assertEqual(qf.page.total, 105)
        self.assertEqual(qf.page.pages, 11)
        self.assertEqual(qf.page.has_next, True)
        self.assertEqual(qf.page.has_prev, True)
        self.assertEqual(len(qf.page.items), 10)

   # def test_nested(self):
    #     f = DynamicDocument.fields

    #     qf = QueryFilter()
    #     qf.add_filter(
    #         FacetFilter('cat', f.category, type=Integer,
    #                     filters=[FacetFilter('manu', f.manufacturer),
    #                              FacetFilter('manu_country', f.manufacturer_country)])
    #     )

    #     sq = SearchQuery()
    #     sq = qf.apply(sq, {'cat__manu': ['1:thl', '2:china', '3']})
    #     self.assert_expression(
    #         sq,
    #         {
    #             "query": {
    #                 "filtered": {
    #                     "filter": {
    #                         "or": [
    #                             {
    #                                 "and": [
    #                                     {
    #                                         "term": {"category": 1},
    #                                         "term": {"manufacturer": "thl"}
    #                                     }
    #                                 ]
    #                             },
    #                             {
    #                                 "and": [
    #                                     {
    #                                         "term": {"category": 2},
    #                                         "term": {"manufacturer_country": "china"},
    #                                     }
    #                                 ]
    #                             },
    #                             {
    #                                 "term": {"category": 3}
    #                             }
    #                         ]
    #                     }
    #                 }
    #             }
    #         }
    #     )
