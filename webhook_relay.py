#!/usr/bin/env python3

import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import json
from functools import reduce
import re


class Server(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_json({
            'success': False,
            'message': 'Wrong method, POST expected'
        }, 400)

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
                "@here {author} uploaded **{title}** at {url}".format(
                    author=data["author"][:256],
                    title=data["title"][:256],
                    url=data["url"][:256]
                )
        }
        print("POST head")
        self.relay_json(post_data)
        # requests.post(config["discordWebhookURL"], data=post_data)

        descriptions = split_text(filter_text(data["description"]), 2048)
        page = 1
        for description in descriptions:
            post_data = {
                "embeds": [{
                    "type": "rich",
                    "description": description
                }]
            }
            if page == 1:
                post_data["embeds"][0]["title"] = data["title"][:256]
            print("POST description {}".format(page))
            page += 1

            self.relay_json(post_data)
            # requests.post(config["discordWebhookURL"], data=post_data)

        return None

    def relay_json(self, data):
        requests.post(
            config["discordWebhookURL"],
            data=json.dumps(data).encode('utf-8'),
            headers={
                "Content-Type": "application/json"
            }
        )

    def send_json(self, obj, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())


def filter_text(text):
    paragraphs = text.split("\n")

    def try_match(line):
        for regexp in patterns:
            if regexp.match(line):
                return False
        return True

    # Filter paragraphs according to config
    paragraphs = [paragraph for paragraph in paragraphs if try_match(paragraph)]

    return "\n".join(paragraphs)


def split_text(text, limit):
    def paragraph_splitter(result, paragraph):
        if len(paragraph) <= limit:
            # If a paragraph can fit in one message, just add it
            result.append(paragraph)
        else:
            # If a paragraph is too long, split it
            while len(paragraph):
                if len(paragraph) > limit:
                    # Remaining portion still too long
                    # Try to split at the last space possible
                    idx = paragraph.rfind(' ', 0, limit - 5) + 1
                    if idx < 1:
                        # If no space found, split as far as possible
                        idx = limit - 5

                    # Add the chopped-off portion, proceed with rest
                    result.append(paragraph[:idx])
                    paragraph = paragraph[idx:]
                else:
                    # Remaining portion OK, just add it
                    result.append(paragraph)
                    paragraph = ""

                if len(paragraph):
                    # If this was not the last portion, add continuation mark
                    result[-1] += "[...]"

        return result

    if limit < 6:
        raise RuntimeError("Limit too narrow to split")

    # Split text into paragraphs
    paragraphs = text.split("\n")

    # Split up paragraphs that are too long
    paragraphs = reduce(paragraph_splitter, paragraphs, [])

    # Each paragraph should already be small enough
    for paragraph in paragraphs:
        assert(len(paragraph) < limit)

    # Assemble chunks as large as possible out of paragraphs
    result = []
    candidate = ""
    quota = limit
    for paragraph in paragraphs:
        if len(paragraph) + 1 <= quota:
            # We still have space for the paragraph + "\n"
            if len(candidate) > 0:
                candidate += "\n"
                quota -= 1
            candidate += paragraph
            quota -= len(paragraph)
        else:
            # We can't add another paragraph, output current chunk
            if len(candidate) > 0:
                result.append(candidate)
                candidate = ""
                quota = limit
            assert(len(paragraph) < quota)

            # Start a new candidate chunk
            candidate += paragraph
            quota -= len(paragraph)

    # Add last chunk, if non-empty
    if len(candidate.strip()):
        result.append(candidate)

    # Strip extra "\n"
    result = [part.strip() for part in result]

    for part in result:
        assert(len(part) < limit)

    return result


if __name__ == '__main__':
    global config, patterns
    try:
        with open("config.json") as config_file:
            config = json.load(config_file)
    except IOError:
        print("Error reading config file")
        exit(1)

    patterns = []
    for pattern in config.get("filters", []):
        patterns.append(re.compile(pattern))

    httpd = HTTPServer((config["host"], config["port"]), Server)
    print(time.asctime(), 'Server UP - %s:%s' % (config["host"], config["port"]))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print(time.asctime(), 'Server DOWN - %s:%s' % (config["host"], config["port"]))
