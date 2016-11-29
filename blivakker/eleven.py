"""
Eleven
Blivakker
Ticket link: https://app.assembla.com/spaces/competitormonitor/tickets/5707-blivakker-%7C-cocopanda-finland-%7C-eleven/details
"""

import os
from collections import namedtuple
from urlparse import urljoin

from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader
from product_spiders.phantomjs import PhantomJS
from product_spiders.utils import extract_price
from scrapy import signals
from scrapy.http import Request
from scrapy.selector import Selector
from scrapy.spiders import BaseSpider
from scrapy.utils.response import get_base_url
from scrapy.xlib.pydispatch import dispatcher

HERE = os.path.abspath(os.path.dirname(__file__))
SHIPPING_PRICE = 120
IN_STOCK_MSG = u'in_stock'


class ElevenSpider(BaseSpider):
    name = 'eleven.fi'
    allowed_domains = ['eleven.se']
    start_urls = ('http://eleven.se/en/',)

    def __init__(self, *args, **kwargs):
        super(ElevenSpider, self).__init__(*args, **kwargs)
        dispatcher.connect(self.spider_closed, signals.spider_closed)
        self.browser = PhantomJS.create_browser()

    def spider_closed(self):
        self.browser.close()

    def parse(self, response):
        base_url = get_base_url(response)
        categories = response.xpath('//div[@id="main-menu-wrapper"]/nav/ul/li/a[not(contains(text(), "BRANDS"))]/@href').extract()
        for category in categories:
            yield Request(urljoin(base_url, category), callback=self.parse_category)

    def parse_category(self, response):
        base_url = get_base_url(response)
        products = response.xpath('//div[@id="d-primary"]/div[@class="product-grid"]/div/a/@href').extract()
        for product in products:
            yield Request(urljoin(base_url, product), callback=self.parse_product)

        pagination = response.xpath('//div[@class="gui-pager"]')
        next_page = pagination.xpath('./a[contains(@class, "pager-circle-next")]/@href').extract_first()
        if next_page:
            yield Request(urljoin(base_url, next_page), callback=self.parse_category)
        else:
            for page in pagination.xpath('./a/@href').extract():
                yield Request(urljoin(base_url, page), callback=self.parse_category)

    def parse_product(self, response):
        base_url = get_base_url(response)
        products = []
        variants = response.xpath('//div[@id="pr-choose-variant"]')
        if not variants:
            selector = Selector(response=response)
            item = self.create_single_product(selector)
            products.append(item)
        else:
            for option_id in response.xpath('//div[@id="pr-alt"]//div[contains(@class, "pr-alt-item")]/@data-id').extract():
                self.browser.get(response.url + '#{0}'.format(option_id))
                variant_selector = Selector(text=self.browser.page_source)
                # TODO: add url to variant_selector
                item = self.create_single_product(variant_selector)
                products.append(item)

        for product in products:
            item = ProductLoader(response=response, item=Product())

            item.add_value('name',          product.name)
            item.add_value('url',           product.url)
            item.add_value('image_url',     product.image_url)
            item.add_value('brand',         product.brand)
            item.add_value('category',      product.category)
            item.add_value('sku',           product.sku)
            item.add_value('identifier',    product.id)
            item.add_value('price',         product.price)
            item.add_value('shipping_cost', product.shipping)
            item.add_value('stock',         product.stock)

            yield item.load_item()

    def create_single_product(self, selector):

        product = namedtuple('Item', ['name', 'url', 'image_url', 'brand', 'category', 'sku', 'id', 'price', 'shipping', 'stock'])

        name = selector.xpath('//div[@id="product"]/h1/text()').extract_first()
        product.name = name

        url = selector.response.url
        product.url = url

        image_url = selector.xpath('//div[@id="ImageSwitch"]//img/@src').extract_first()
        product.image_url = urljoin(get_base_url(selector.response), image_url)

        brand = selector.xpath('//div[@id="product"]//*[@class="pr-brand-text"]/a/text()').extract_first()
        product.brand = brand

        categories = selector.xpath('//div[@id="product"]/div[@class="breadcrumbs"]//a/span/text()').extract()
        product.category = ' '.join(categories)

        sku = selector.xpath('//form[@id="pr-form"]//input[@name="sku"]/@value').extract_first()
        product.sku = sku

        identifier = selector.xpath('//form[@id="pr-form"]//input[@name="i"]/@value').extract_first()
        product.id = identifier

        price = extract_price(selector.xpath('//div[@id="product"]//span[contains(@class, "pr-price")]/span/text()').extract_first())
        product.price = price

        if price >= 1000:
            product.shipping = 0
        else:
            product.shipping = SHIPPING_PRICE

        stock = selector.xpath('//div[@id="pr-info-stock"]/span[@class="availability"]/text()').extract_first()
        if stock == IN_STOCK_MSG:
            product.stock = 1
        else:
            product.stock = 0

        return product
