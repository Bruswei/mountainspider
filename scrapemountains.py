#!/usr/bin/env python
# -*- coding: utf-8 -*-

from scrapy import Spider
from scrapy.spiders import CrawlSpider, Rule
from scrapy.crawler import CrawlerProcess
from scrapy.selector import Selector
from scrapy.linkextractors import LinkExtractor
import json
import os
import re
from html2text import html2text
import googlemaps

google_api_key = "AIzaSyAjvERqHKyxaqCnEw3XBiy3PZt7L8gfC4A"

class MountainSpider(CrawlSpider):
    """Mountain spider"""

    name = "mountainspider"
    allowed_domains = ['www.ii.uib.no']
    start_urls = [
        "https://www.ii.uib.no/~petter/mountains.html"
    ]
    rules = (
        Rule(LinkExtractor(allow=('mountains.html')), callback='parse_table'),
        Rule(LinkExtractor(allow=('[1|10|15|20|30|40|50]00mtn\/[a-zA-Z]*\.html')), callback='parse_mountain', follow=True),
        Rule(LinkExtractor(allow=('trip-report.html')), callback='parse_tripreport'),
    )
    mountains = []
    mountainlist = []


    def parse_table(self, response):
        """ Parse mountain table from front page """

        # This is a dirty hack to prevent scrapy from crawling the same page several times
        # (Which it shouldn't do in the first place.)
        if len(self.mountainlist) > 0:
            return

        # Mountain table is the second table on the website
        mountainTable = Selector(response=response).xpath('//table[1]/tr')

        for rownum, row in enumerate(mountainTable):
            # The rows we are interested in are row 3 to 1351
            if rownum > 2 and rownum < 1352: 
                number = row.xpath('.//td[1]/text()').extract_first()
                name = row.xpath('.//td[2]/a/text()').extract_first()
                url = row.xpath('.//td[2]/a/@href').extract_first()
                height = row.xpath('.//td[3]/text()').extract_first()
                when = row.xpath('.//td[4]/text()').extract_first()
                comment = row.xpath('.//td[5]/text()').extract_first()
            
                height_re = re.search(r'^(\d+)[ ]*m', height)
                if height_re:
                    height = int(height_re.group(1))
                else:
                    height = 0

                js = dict()
                js["number"] = number
                js["name"] = name
                js["url"] = url
                js["height"] = height
                js["when"] = when
                js["comment"] = comment

                if name: 
                    self.mountainlist.append(js)


    def parse_mountain(self, response):
        """ Parse data from mountain info pages """

        # Information from top table
        page = Selector(response=response)
        title = page.xpath('//h2/text()|//a/text()').extract_first() or ""
        infoTable = page.xpath('//table')

        rows = []
        for i in range(1,12):
            rows.append(infoTable.xpath('.//li[' + str(i) + ']//text()').extract_first() or "")

        # Strip unnecessary newlines
        title = title.strip('\n').strip(' ')
        rows = [ ' '.join(row.replace('\n', ' ').strip(' ').strip('.').split()) for row in rows ] 

        # Extract information
        # On those pages where name is not title, first row is title
        name = title or rows[0]
        
        # Url from response
        url = response.url

        height = ""
        pf = ""
        location = ""
        climbed = ""
        difficulty = ""
        geocode = ""
        info = []

        for row in rows: 
            height_re = re.search(r'^(\d+)[ ]*m', row)
            height_alt_re = re.search(r'^Elevation[:]? (\d+)[ ]*m', row)
            pf_re = re.search(r'factor[:]? (\d+)[ ]*m', row)
            location_re = re.search(r'Location[:]?[ ]?(.+)',row)
            climbed_re = re.search(r'Climbed[:]? (.+)',row)
            difficulty_re = re.search(r'Difficulty[:]? (.+)',row)

            if height_re:
                height = int(height_re.group(1))
            elif height_alt_re:
                height = int(height_alt_re.group(1))
            elif pf_re:
                pf = int(pf_re.group(1))
            elif location_re:
                location = location_re.group(1).replace('`', '').strip(' ')
            elif climbed_re:
                climbed = climbed_re.group(1).strip('.')
            elif difficulty_re:
                difficulty = difficulty_re.group(1).strip('.')
            elif row and row != name:
                info.append(row + '.')

        # Get geocode
        gmaps = googlemaps.Client(key=google_api_key)
        geocode_request = gmaps.geocode(name)
        if geocode_request:
            geocode = geocode_request[0]

        rawText = (''.join(Selector(response=response)
        .xpath('//body/text()|//body/strong|//body/p|//body/a|//body/strong/a|//body/p/a')
        .extract())
        .replace('<p></p>','')
        .replace('<strong>How to get there:</strong>','<h1>How to Get There</h1>')
        .replace('<strong>Route description:</strong>','<h1>Route Description</h1>')
        .replace('<strong>Trip report:</strong>','<h1>Trip Report</h1>')
        .replace('<strong>Comments:</strong>','<h1>Comments</h1>'))

        markdownText = html2text(rawText).replace("\n\n", '-----').replace("\n", ' ').replace('-----', "\n\n")

        # Build json struct
        js = dict()                  
        js["url"] = url
        js["name"] = name
        js["height"] = height
        js["primary_factor"] = pf
        js["location"] = location
        js["climbed"] = climbed
        js["difficulty"] = difficulty
        js["info"] = info
        js["geocode"] = geocode
        js["content"] = markdownText

        self.mountains.append(js)


    def parse_tripreport(self, response):
        """Parse trip reports"""


spider = MountainSpider()
process = CrawlerProcess({
    'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
    'LOG_LEVEL': 'DEBUG'
})

process.crawl(spider)
process.start()


with open("mountain_list.json", "w") as file:
    file.write(json.dumps(spider.mountainlist, sort_keys=True, indent=4))

with open("mountains.json", "w") as file:
    file.write(json.dumps(spider.mountains, sort_keys=True, indent=4))


