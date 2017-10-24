import re
import requests
from statistics import mode, StatisticsError
from collections import namedtuple

LINKS = open("links.txt", encoding="utf-8", mode="r")
CORRECT = open("correct.txt", encoding="utf-8", mode="w")
RAW = open("raw.txt", encoding="utf-8", mode="w")


def get_unique_links():
    return list(set(filter(lambda x: not x.isspace(), LINKS.readlines())))


class Link:
    def __init__(self, link):
        pass

    def get_text(self):
        pass


class PastebinLink(Link):
    def __init__(self, link):
        super(PastebinLink, self).__init__(link)
        get = re.compile(r'(https?://)?(www.)?(pastebin.com/)(?P<id>.*)$')
        match = get.fullmatch(link)
        if match is None:
            raise ValueError("Expected a pastebin.com link, found something else")
        self.id = get.fullmatch(link).group('id')

    def get_text(self):
        url = 'https://pastebin.com/raw/%s' % self.id
        return requests.get(url).text


class Response:
    def __init__(self, text):
        data = text.split("\r\n")
        try:
            data = data[list(map(lambda q: "(Вес 2.5%)" in q, data)).index(True) + 1:]
        except ValueError:
            pass
        try:
            data = data[list(map(lambda q: "Балл теста:" in q, data)).index(True) + 1:]
        except ValueError:
            pass
        try:
            data = data[:list(map(lambda q: "Балл:" in q, data)).index(True) + 1]
        except ValueError:
            pass
        data = list(filter(lambda line: line and not line.isspace(), data))
        self.question_text = data[0].strip()
        data.pop(0)
        self.grade = float(re.compile(r'(Балл: )(?P<grade>\d{1,3}\.?\d{0,2})').match(data[-1]).group('grade'))
        data.pop()
        answer = re.compile(r'([\(\[](?P<chosen>[ x])[\)\]])(?P<ind>[а-я])\)\s*(?P<answer_text>.*)$')
        self.answers = []
        for item in data:
            match = answer.fullmatch(item)
            try:
                Ans = namedtuple("Ans", 'ind, text, chosen')
                self.answers.append(Ans(match.group('ind'), match.group('answer_text'), match.group('chosen') == "x"))
            except AttributeError:
                print(data)
                raise AttributeError("Something went wrong while parsing this question")
        self.answers.sort()

    def __str__(self):
        s = self.question_text + "\n"
        for ans in self.answers:
            s += "[%s]%s) %s\n" % ("x" if ans.chosen else " ", ans.ind, ans.text)
        s += "Балл: %f\n" % self.grade
        return s

    def __lt__(self, other):
        if not isinstance(other, Response):
            raise TypeError("Can't compare Responses with anything other than Responses")
        return (self.question_text, -self.grade) < (other.question_text, -other.grade)


def parse_text(text):
    approx_questions = text.split("Вопрос")
    return list(map(lambda q: Response(q), filter(lambda q: "Балл:" in q, approx_questions)))


class Question:
    def __init__(self, text, answers):
        self.question_text = text
        self.answers = list(map(lambda d: {'ind': d.ind, 'text': d.text}, answers))
        self.responses = []
        self.guessed = None
        self.is_definitely_correct = False

    def add_response(self, response):
        if not isinstance(response, Response):
            raise TypeError("Only responses of from the Response class may be added")
        else:
            mask = ""
            for ans in response.answers:
                if ans.chosen:
                    mask += "1"
                else:
                    mask += "0"
            self.responses.append({'mask': mask, 'grade': response.grade})

    def guess(self):
        possible_values = []
        total_ans_count = len(self.answers)
        for resp in self.responses:
            if resp['grade'] == 100.0:
                self.is_definitely_correct = True
                self.guessed = resp['mask']
                return
            else:
                chosen_count = sum(map(int, list(resp['mask'])))
                g = resp['grade']
                if g == 0:
                    continue
                try:
                    x = int(chosen_count / (1 - g / 100))
                    if 0 <= x <= total_ans_count:
                        possible_values.append(x)
                except ZeroDivisionError:
                    pass
                try:
                    x = int(chosen_count / (1 + g / 100))
                    if 0 <= x <= total_ans_count:
                        possible_values.append(x)
                except ZeroDivisionError:
                    pass
        try:
            correct_ans_count = mode(possible_values)
            self.guessed = correct_ans_count * "1" + (total_ans_count - correct_ans_count) * "0"
        except StatisticsError:
            self.guessed = None

    def __str__(self):
        s = self.question_text + "\n"
        for i in range(len(self.answers)):
            ans = self.answers[i]
            if self.guessed is None or self.guessed[i] == "0":
                s += "[ ]%s) %s\n" % (ans['ind'], ans['text'])
            else:
                s += "[x]%s) %s\n" % (ans['ind'], ans['text'])
        if self.is_definitely_correct:
            s += "Балл: 100%\n"
        elif self.guessed is not None:
            s += "Балл: 99%\n"
        else:
            s += "Недостаточно данных для того, чтобы угадать правильный ответ на вопрос\n"
        return s


link_parsers = Link.__subclasses__()
responses = []
for link in LINKS.readlines():
    for LinkParser in link_parsers:
        try:
            raw_questions = parse_text(LinkParser(link.rstrip()).get_text())
            responses += raw_questions
            break
        except ValueError:
            continue

responses.sort()
question_dict = dict()
for item in responses:
    if question_dict.get(item.question_text) is None:
        question_dict[item.question_text] = Question(item.question_text, item.answers)
    question_dict[item.question_text].add_response(item)
    RAW.write(str(item) + "\n")
for key in sorted(question_dict.keys()):
    question_dict[key].guess()
    CORRECT.write(str(question_dict[key]) + "\n")