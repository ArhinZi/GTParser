from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import xlrd
import sys
from time import sleep
from pprint import pprint
import csv
import random
import threading
from threading import Thread


class Parser(Thread):
    DEBUG = True
    index = 0
    user_agent_list = []
    chrome = None
    wait = None
    sh = None
    first = 0
    STOP = False

    def debug(self, string):
        if(self.DEBUG):
            print("Thread:", self.index, ":", string)

    def __init__(self, first=0, index=0):
        Thread.__init__(self)
        self._stop_event = threading.Event()

        self.index = index

        self.debug('Loading User Agents')
        with open('user-agents.txt') as f:
            self.user_agent_list = f.readlines()

        with open('res%s.csv'%self.index, mode="w", encoding='utf-8') as file:
            fieldnames = ['word', 'common_mean', 'pronunciation',
                          'more_mean', 'definition', 'synonyms', 'example']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            writer.writeheader()

        self.debug('Open Links')
        book = xlrd.open_workbook("testlink%s.xlsx"%self.index)
        self.sh = book.sheet_by_index(0)

    def get_driver(self):
        chrome_options = webdriver.ChromeOptions()
        i = random.randint(0, 1000)
        user_agent = self.user_agent_list[i]
        self.debug("Set User Agent: "+user_agent)

        chrome_options.add_argument("user-agent=%s" % user_agent)
        chrome_options.add_argument('--lang=en')
        self.chrome = webdriver.Chrome(options=chrome_options)

        self.wait = WebDriverWait(self.chrome, 5)

    def has_class(self, elem, class_name):
        if(class_name in elem.get_attribute("class").split(" ")):
            return True
        else:
            return False

    def scrap(self, start, stop):
        last_common_mean = last_pronunciation = last_more_mean = last_definition = last_synonyms = last_example = None
        if(stop > self.sh.nrows):
            stop = self.sh.nrows
        if(start < 0 or start > stop-1):
            return False

        res = {}

        self.debug("Start scraping")
        for row in range(start, stop):
            if(self.STOP):
                break
            word = self.sh.cell_value(rowx=row, colx=1)
            _lang = (self.sh.cell_value(
                rowx=row, colx=0).split("#")[1]).split("/")[:-1]
            # print(_lang)
            self.chrome.get(
                "https://translate.google.com/m/translate#view=home&op=translate&sl=%s&tl=%s&text=%s" % (_lang[0], _lang[1], word))
            sleep(0.1)

            common_mean = pronunciation = more_mean = definition = synonyms = example = "None"

            self.wait.until(lambda driver: self.chrome.execute_script(
                "return document.readyState") == "complete")
            sleep(1)
            while not self.STOP:
                for i in range(2):
                    try:
                        common_mean = self.wait.until(
                            EC.visibility_of_element_located(
                                (By.CSS_SELECTOR, ".result-dict-wrapper .tlid-translation.translation > span"))
                        ).get_attribute('textContent')
                        if(last_common_mean == common_mean):
                            continue
                        break
                    except:
                        continue

                if(self.STOP):
                    break
                if(common_mean == None):
                    self.debug("Runtime error! Please, solve the problem!")
                    print("Current row:", row)
                    sleep(5)
                    continue
                else:
                    (pronunciation, more_mean, definition,
                     synonyms, example) = self.parse_more()
                    # if(last_pronunciation == pronunciation):
                    #     pronunciation = "None"
                    # if(last_more_mean == more_mean):
                    #     more_mean = "None"
                    # if(last_definition == definition):
                    #     definition = "None"
                    # if(last_synonyms == synonyms):
                    #     synonyms = "None"
                    # if(last_example == example):
                    #     example = "None"
                    break

            if(self.STOP):
                print("Current row:", row)
            last_common_mean, last_pronunciation, last_more_mean, last_definition, last_synonyms, last_example = (
                common_mean, pronunciation, more_mean, definition, synonyms, example)
            res[word] = list([common_mean, pronunciation,
                              more_mean, definition, synonyms, example])
            # input()
            self.chrome.get(
                "https://translate.google.com/m/translate#view=home&op=translate&sl=en&tl=bn")
            sleep(0.1)

        return res

    def parse_more(self):
        try:
            pronunciation = self.chrome.find_element_by_css_selector(
                ".result-transliteration-container .transliteration-content").get_attribute('textContent')
        except:
            pronunciation = "None"

        try:
            _right = self.chrome.find_element_by_css_selector(
                ".gt-lc.gt-lc-mobile .gt-cc-l .gt-cd")
            _display = _right.value_of_css_property('display')
            if(_display == 'none'):
                raise Exception("More Mean: display(none)")
        except:
            _right = None

        if(_right is not None):
            more_mean = ""
            for elem in _right.find_elements_by_css_selector(
                    ".gt-cd-c .gt-baf-table tbody tr"):
                if(self.has_class(elem, "gt-baf-entry")):
                    _text = elem.find_element_by_css_selector(
                        "div.gt-baf-term-text-parent span span").get_attribute('textContent') + ":"

                    _word_list = map(lambda x: x.get_attribute(
                        'textContent'), elem.find_elements_by_css_selector("div.gt-baf-translations span"))
                    _words = ", ".join(_word_list)

                    _text = _text + " " + _words + "; "

                else:
                    try:
                        _text = elem.find_element_by_css_selector(
                            "div.gt-baf-pos-head span").get_attribute('textContent')
                    except:
                        _text = " "
                    _text = "[%s]{ " % (_text)
                    if(not (more_mean == "")):
                        _text = "} "+_text
                more_mean += _text
        else:
            more_mean = "None"

        try:
            _left = self.chrome.find_element_by_css_selector(
                ".gt-lc.gt-lc-mobile .gt-cc-r")
            _display = _left.find_element_by_css_selector(
                ".gt-cd").value_of_css_property('display')
            if(_display == 'none'):
                raise Exception("More Mean: display(none)")
        except:
            _left = None

        if(_left is not None):
            if(not(_left.find_element_by_css_selector(".gt-cd-mmd").value_of_css_property('display') == 'none')):
                definition = ""
                for elem in _left.find_elements_by_css_selector(".gt-cd-mmd .gt-cd-c .gt-cd-pos, .gt-cd-mmd .gt-cd-c .gt-def-list"):
                    _last_text = ""
                    if(self.has_class(elem, "gt-cd-pos")):
                        try:
                            _text = elem.get_attribute('textContent')
                        except:
                            _text = " "
                        _text = "[%s]{ " % (_text)
                        if(not (definition == "")):
                            _text = "} "+_text
                    elif(self.has_class(elem, "gt-def-list")):
                        _text = ""
                        for info in elem.find_elements_by_css_selector(".gt-def-info"):
                            _subtext = info.find_element_by_css_selector(
                                ".gt-def-num").get_attribute('textContent') + ": "
                            _subtext += info.find_element_by_css_selector(
                                ".gt-def-row").get_attribute('textContent')
                            try:
                                _subtext += " (" + info.find_element_by_css_selector(
                                    ".gt-def-example").get_attribute('textContent') + ") "
                            except:
                                pass

                            # if(_last_subtext == _subtext):
                            #     break
                            _last_subtext = _subtext
                            _text += _subtext

                    definition += _text
                    # print(_text)
                definition += "}"
            else:
                definition = "None"

            if(not(_left.find_element_by_css_selector(".gt-cd-mss").value_of_css_property('display') == 'none')):
                synonyms = ""
                for elem in _left.find_elements_by_css_selector(".gt-cd-mss .gt-cd-c .gt-cd-pos, .gt-cd-mss .gt-cd-c .gt-syn-list"):
                    if(self.has_class(elem, "gt-cd-pos")):
                        try:
                            _text = elem.get_attribute('textContent')
                        except:
                            _text = " "
                        _text = "[%s]{ " % (_text)
                        if(not (synonyms == "")):
                            _text = "} "+_text
                    elif(self.has_class(elem, "gt-syn-list")):
                        _syn_list = map(lambda x: x.get_attribute(
                            'textContent'), elem.find_elements_by_css_selector(".gt-syn-row span span"))
                        _text = ", ".join(_syn_list)
                    synonyms += _text
                synonyms += "}"
            else:
                synonyms = "None"

            if(not(_left.find_element_by_css_selector(".gt-cd-mex").value_of_css_property('display') == 'none')):
                example = map(lambda x: x.get_attribute(
                    'textContent'), _left.find_elements_by_css_selector(".gt-cd-mex .gt-cd-c .gt-ex-info .gt-ex-top .gt-ex-text"))
                example = '; '.join(example)
            else:
                example = "None"

        else:
            definition = synonyms = example = "None"

        return (pronunciation, more_mean, definition, synonyms, example)

    def save_data(self, res):
        self.debug('Save data')
        with open('res%s.csv'%self.index, mode="a", encoding='utf-8') as file:
            fieldnames = ['word', 'common_mean', 'pronunciation',
                          'more_mean', 'definition', 'synonyms', 'example']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            for key in res.keys():
                writer.writerow(
                    {'word': key, 'common_mean': res[key][0], 'pronunciation': res[key][1], 'more_mean': res[key][2], 'definition': res[key][3], 'synonyms': res[key][4], 'example': res[key][5]})

    def run(self):
        #
        res = {}
        k = 500
        for i in range(self.first, self.sh.nrows, k):
            if(self.STOP):
                break
            self.get_driver()
            self.chrome.get("https://translate.google.com")
            sleep(5)
            # input()
            res = self.scrap(i, i+k)
            self.save_data(res)
            self.chrome.close()
        self.debug("FINISHED!!!")


if __name__ == "__main__":

    
    k = input("Threads: ")
    threads = [None]*int(k)
    for i in range(int(k)):
 
        # n = input('Start row:')
        threads[i] = Parser(first=0, index=i)
        threads[i].setDaemon(True)
        threads[i].start()
    # my_thread.join()

    while True:
        # if(not threads[i].is_alive()):
        #     break
        str = input()

        if(str == 'exit'):
            for i in threads:
                i.STOP = True
            print('-----Stopping')
            while True:
                # print(all(x.is_alive() for x in threads))
                if not any(x.is_alive() for x in threads):
                    break
                sleep(0.1)
            break
        else:
            print("Unknown command:'%s'" % str)
