#!/usr/bin/env python3

import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import json
from functools import reduce


class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_json({
            'success': False,
            'message': 'Wrong method, POST expected'
        }, 400)

    def do_POST(self):
        if self.headers.get("Content-type") != "application/json":
            print(self.headers)
            self.send_json({
                'success': False,
                'message': 'Wrong content type (\'application/json\' expected)'
            }, 400)
        else:
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_body)

            if data.get('authKey') == config['authKey']:
                error = self.relay(data)
                if not error:
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False, 'message': error})
            else:
                self.send_json({
                    'success': False,
                    'message': 'Auth key missing or incorrect'
                }, 403)

    def relay(self, data):
        if "url" not in data:
            return "No video URL received"
        if "author" not in data:
            return "No video author name received"
        if "title" not in data:
            return "No video title name received"
        if "description" not in data:
            return "No video description received"

        post_data = {
            "content":
                "@-here {author} uploaded **{title}** at {url}".format(
                    author=data["author"],
                    title=data["title"],
                    url=data["url"]
                )
        }
        print("POST head")
        requests.post(config["discordWebhookURL"], data=post_data)

        descriptions = split_text(data["description"], 2000)
        page = 1
        for description in descriptions:
            post_data = {
                "content": description
            }
            print("POST description {}".format(page))
            page += 1

            requests.post(config["discordWebhookURL"], data=post_data)

        return None

    def send_json(self, obj, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())


def split_text(text, limit, delimiter="\n"):
    def paragraph_splitter(result, paragraph):
        if len(paragraph) <= limit:
            result.append(paragraph)
        else:
            while len(paragraph):
                result.append("{}[...]".format(paragraph[:limit - 5]))
                paragraph = paragraph[limit - 5:]

        return result

    if limit < 6:
        raise RuntimeError("Limit too narrow to split")

    paragraphs = text.split(delimiter)

    paragraphs = reduce(paragraph_splitter, paragraphs, [])

    result = []
    candidate = ""
    quota = limit
    for paragraph in paragraphs:
        if len(paragraph) + 1 <= quota:
            if len(candidate) > 0:
                candidate += delimiter
                quota -= 1
            candidate += paragraph
            quota -= len(paragraph)
        else:
            if len(candidate) > 0:
                result.append(candidate)
                candidate = ""
                quota = limit
            if len(paragraph) <= quota:
                candidate += paragraph
                quota -= len(paragraph)
            else:
                raise RuntimeError("Text splitting failed")

    if len(candidate):
        result.append(candidate)

    return result


if __name__ == '__main__':
    global config
    try:
        with open("config.json") as config_file:
            config = json.load(config_file)
    except IOError:
        print("Error reading config file")
        exit(1)

    httpd = HTTPServer((config["host"], config["port"]), Server)
    print(time.asctime(), 'Server UP - %s:%s' % (config["host"], config["port"]))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print(time.asctime(), 'Server DOWN - %s:%s' % (config["host"], config["port"]))
