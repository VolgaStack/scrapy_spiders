"""
Eleven
Blivakker
Ticket link: https://app.assembla.com/spaces/competitormonitor/tickets/5707-blivakker-%7C-cocopanda-finland-%7C-eleven/details
"""

import json
import os
from urlparse import urljoin

from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader
from scrapy.http import Request
from scrapy.spiders import BaseSpider
from scrapy.utils.response import get_base_url

HERE = os.path.abspath(os.path.dirname(__file__))
SHIPPING_PRICE = 120
IN_STOCK_MSG = u'in_stock'


class ElevenSpider(BaseSpider):
    name = 'eleven.fi'
    allowed_domains = ['eleven.se']
    start_urls = ('http://eleven.se/en/',)

    def parse(self, response):
        base_url = get_base_url(response)
        categories = response.xpath(
            '//div[@id="main-menu-wrapper"]/nav/ul/li/a[not(contains(text(), "BRANDS"))]/@href').extract()
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
        products_data = {}
        js = response.xpath('//script[contains(text(), "window.dataLayer.push")]/text()').extract_first()
        collecting_product = False
        extracting = ['productNumbers', 'productBarcodes', 'productPricesInclVat', 'subProductTitles']
        for line in js.split('\n'):
            if 'window.dataLayer.push({' in line:
                collecting_product = True
                continue
            if '});' in line and collecting_product:
                break
            if collecting_product:
                attr_data = [a.strip() for a in line[:-1].split(':')]
                key = attr_data[0].replace("'", '')
                if key in extracting:
                    products_data[key] = eval(attr_data[1])
                    if isinstance(products_data[key], str):
                        products_data[key] = [products_data[key]]

        products = []
        product_options = response.xpath('//script[contains(text(), "var productItem")]/text()').extract_first()
        # if there are product options, that means that i need to find for each option it's price, name and picture.
        # price, name, picture and barcode is in products list
        # id, sku and image is in options dict
        if product_options:
            json_clean = product_options.replace('var productItems =', '').strip()
            options = json.loads(json_clean)
            # here i create a product for every option. Product and option matched via SKU
            for key, option in options.iteritems():
                for index, sku_code in enumerate(products_data['productNumbers']):
                    if sku_code == option[u'sProductNumber']:
                        item = {'id': option[u'iSubProductId'],
                                'sku': option[u'sProductNumber'],
                                'image': option.get([u'sImgBigUrl'], ''),
                                'name': products_data['subProductTitles'][index].encode('utf-8'),
                                'price': products_data['productPricesInclVat'][index],
                                'barcode': products_data['productBarcodes'][index],
                                }
                        if IN_STOCK_MSG in option[u'sStockXhtml']:
                            item['stock'] = 1
                        else:
                            item['stock'] = 0

                        products.append(item)

        # if there is no product options i can leave this fields empty and take values from product page
        else:
            products.append({'barcode': products_data['productBarcodes'], })

        # now we can create items based on our products list
        for product in products:
            item = ProductLoader(response=response, item=Product())

            name = response.xpath('//div[@id="product"]/h1/text()').extract_first()
            option_name = product.get('name', '')
            item.add_value('name', name + ' ' + option_name if option_name else name)

            item.add_value('url', response.url)

            image_url = response.xpath('//div[@id="ImageSwitch"]//img/@src').extract_first()
            option_image = product.get('image', '')
            item.add_value('image_url',
                           urljoin(response.url, option_image) if option_image else urljoin(response.url, image_url))

            brand = response.xpath('//div[@id="product"]//*[@class="pr-brand-text"]/a/text()').extract_first()
            item.add_value('brand', brand)

            categories = response.xpath('//div[@id="product"]/div[@class="breadcrumbs"]//a/span/text()').extract()
            for category in categories:
                item.add_value('category', category)

            sku = response.xpath('//form[@id="pr-form"]//input[@name="sku"]/@value').extract_first()
            option_sku = product.get('sku', '')
            item.add_value('sku', option_sku if option_sku else sku)

            identifier = response.xpath('//form[@id="pr-form"]//input[@name="i"]/@value').extract_first()
            option_identifier = product.get('id', '')
            item.add_value('identifier', option_identifier if option_identifier else identifier)

            price = response.xpath('//div[@id="product"]//span[contains(@class, "pr-price")]/span/text()').extract_first()
            option_price = product.get('price', '')
            item.add_value('price', option_price if option_price else price)

            if price >= 1000:
                item.add_value('shipping_cost', 0)
            else:
                item.add_value('shipping_cost', SHIPPING_PRICE)

            stock = response.xpath('//div[@id="pr-info-stock"]/span[@class="availability"]/text()').extract_first()
            option_stock = product.get('stock', '')
            if option_stock != '':
                item.add_value('stock', option_stock)
            elif IN_STOCK_MSG in stock:
                item.add_value('stock', 1)
            else:
                item.add_value('stock', 0)

            yield item.load_item()
