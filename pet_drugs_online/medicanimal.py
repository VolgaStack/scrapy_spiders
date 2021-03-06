"""
Medic Animal
Pet Drugs Online
Ticket link: https://app.assembla.com/spaces/competitormonitor/tickets/5604-pet-drugs-online---new-site---medic-animal/details
"""

import os
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
SHIPPING_PRICE = 2.99


class MedicAnimalSpider(BaseSpider):
    name = 'medicanimal.com'
    allowed_domains = ['medicanimal.com']
    start_urls = ('https://www.medicanimal.com/',)

    def __init__(self, *args, **kwargs):
        super(MedicAnimalSpider, self).__init__(*args, **kwargs)
        dispatcher.connect(self.spider_closed, signals.spider_closed)
        self.browser = PhantomJS.create_browser()

    def spider_closed(self):
        self.browser.close()

    def parse(self, response):
        base_url = get_base_url(response)
        main_categories = response.xpath('//nav[contains(@class, "main-navigation")]/ul/li[contains(@class, "auto")]/a/@href').extract()
        for category in main_categories:
            yield Request(urljoin(base_url, category), callback=self.parse_product_list)

    def parse_product_list(self, response):
        base_url = get_base_url(response)
        products = response.css('.product-item-inner').xpath('./div/div[@class="product-image"]/a[@class="product-item-image"]/@href').extract()
        for product in products:
            yield Request(urljoin(base_url, product), callback=self.parse_product)

        next_page = response.xpath('//ul[@class="pagination"]/li/a[@rel="next"]/@href').extract_first()
        if next_page:
            yield Request(urljoin(base_url, next_page), callback=self.parse_product_list)

    def parse_product(self, response):
        name = response.xpath('//div[@class="product-details"]/h1/text()').extract_first()
        categories = response.xpath('//div[@id="breadcrumb"]/ol/li/a[not(contains(text(), "Home"))]/text()').extract()
        brand_list = response.xpath('//head/script[@type="text/javascript"]').re(r'manufacturer: ".*",')
        product_id = response.url.split('/')[-1]

        # call for phantomjs only if we were not able to get brandlist from standart response
        if not brand_list:
            self.browser.get(response.url)
            sel = Selector(text=self.browser.page_source)
            brand_list = sel.xpath('//head/script[@type="text/javascript"]').re(r'manufacturer: ".*",')

        variants = response.xpath('//ul[@id="variants-list"]/li')
        variants_generator = (variant for variant in variants if int(variant.xpath('./@data-scale-value').extract_first()) == 1)
        for variant in variants_generator:
            item = ProductLoader(response=response, item=Product())

            variant_name = variant.xpath('./span[@class="variant-list-name"]/text()').extract_first()
            item.add_value('name', name)
            item.add_value('name', variant_name)
            
            variant_price = extract_price(variant.xpath('./span[@class="variant-extras"]/span[contains(@class, "variant-price")]/text()').extract_first())
            item.add_value('price', variant_price)
            
            item.add_value('url', response.url)
            item.add_xpath('image_url', '//div[@class="prod_image_main"]/img/@data-src')

            for brand in brand_list:
                # manufacturer: "Royal canin",
                item.add_value('brand', brand.split(':')[-1].strip()[1:-1])
            
            for category in categories:
                item.add_value('category', category)

            sku = variant.xpath('./@data-variant-code').extract_first()
            item.add_value('sku', sku)
            
            item.add_value('identifier', product_id + '-' + sku)
            
            out_of_stock = variant.xpath('.//span[@class="variant-info"]/span[@class="variant-stockstatus"]')
            if out_of_stock:
                item.add_value('stock', 0)
            else:
                item.add_value('stock', 1)

            if variant_price >= 30:
                item.add_value('shipping_cost', 0)
            else:
                item.add_value('shipping_cost', SHIPPING_PRICE)
        
            yield item.load_item()
