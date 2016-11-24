"""
Total angling
Nash Tackle
Ticket link: https://app.assembla.com/spaces/competitormonitor/tickets/5664-nash-tackle---new-site---total-angling
"""

import os
from decimal import Decimal
from itertools import product
from urlparse import urljoin

from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader
from product_spiders.utils import extract_price
from scrapy.http import Request
from scrapy.spider import BaseSpider
from scrapy.utils.response import get_base_url

IN_STOCK_MSG = u'In stock'
HERE = os.path.abspath(os.path.dirname(__file__))


class TotalAnglingSpider(BaseSpider):
    name = 'totalangling.co.uk'
    allowed_domains = ['totalangling.co.uk']
    start_urls = ('http://www.totalangling.co.uk',)

    def parse(self, response):
        base_url = get_base_url(response)
        categories = response.xpath('//*[@id="nav"]/li[not(contains(@class, "nav-item--home"))]//a/@href').extract()
        for category in categories:
            yield Request(urljoin(base_url, category), callback=self.parse_categories)

    def parse_categories(self, response):
        base_url = get_base_url(response)
        products = response.css('.itemgrid').xpath('./li[@class="item"]/div[@class="product-image-wrapper"]/a/@href').extract()
        for product_url in products:
            yield Request(urljoin(base_url, product_url), callback=self.parse_product)

        next_page = response.css('.pages').xpath('.//ol/li[@class="next"]/a/@href').extract()
        if next_page:
            yield Request(urljoin(base_url, next_page[0]), callback=self.parse_categories)

    def parse_product(self, response):
        name = response.xpath('//div[@class="product-name"]/h1/text()').extract_first()
        price = extract_price(response.xpath('//div[@class="price-box"]/span/span[@class="price"]/text()').extract_first())
        identifier = response.xpath('//*[@id="product_addtocart_form"]/div[@class="no-display"]' +
                                    '/input[@name="product"]/@value').extract_first()

        option_boxes = response.xpath('//div[@id="product-options-wrapper"]/dl/dd/div/select[contains(@class, "product-custom-option")]')
        # first i check if there are any option boxes on a page
        if option_boxes:
            option_list = []
            options = []
            first_time = True
            # then i build a list of options for each option box
            # flag is here to ignore first time we get into loop because first time is default "please select" option
            # after that "please select" is used to distinct between option boxes
            for opt in option_boxes.xpath('./option'):
                if opt.xpath('./@value').extract_first():
                    option_id = opt.xpath('./@value').extract_first()
                    option_price = opt.xpath('./@price').extract_first()
                    option_name = opt.xpath('./text()').extract_first()
                    options.append((option_id, option_name, option_price))
                elif first_time:
                    first_time = False
                else:
                    option_list.append(options)
                    options = []
            option_list.append(options)
            # here i use itertools functionality to build all possible combinations out of list of options
            options_combo = list(product(*option_list))
            # after that compose unique id, name and price for each combination
            for combo in options_combo:
                combo_id = []
                combo_name = []
                combo_price = 0
                for combo_piece in combo:
                    combo_id.append(combo_piece[0])
                    combo_name.append(combo_piece[1])
                    combo_price += Decimal(combo_piece[2])
                loader = self.create_product(response)
                loader.add_value('identifier', identifier + '-' + '-'.join(combo_id))
                loader.add_value('name', name + ' ' + ' '.join(combo_name))
                loader.add_value('price', price + combo_price)
                yield loader.load_item()
        else:
            loader = self.create_product(response)
            loader.add_value('identifier', identifier)
            loader.add_value('name', name)
            loader.add_value('price', price)
            yield loader.load_item()

    def create_product(self, response):
        item = ProductLoader(response=response, item=Product())
        item.add_value('url', response.url)
        item.add_xpath('image_url', '//p[@class="product-image zoom-inside"]/a[@id="zoom1"]/@href')

        categories = response.xpath('//div[@class="breadcrumbs"]/ul/li[not(contains(@class, "home"))]/a/span/text()').extract()
        for category in categories:
            item.add_value('category', category)
        item.add_xpath('brand', '//meta[@itemprop="brand"]/@content')

        sku = response.xpath('//meta[@itemprop="productID"]/@content').extract_first()
        sku_clean = sku.split(':')[-1].strip()
        item.add_value('sku', sku_clean)

        stock = response.xpath('//div[@class="product-type-data"]/p').css('.availability').xpath('./span/text()').extract_first()
        if stock == IN_STOCK_MSG:
            item.add_value('stock', 1)
        else:
            item.add_value('stock', 0)

        item.add_value('shipping_cost', '')
        return item
