import os
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.prompts import ChatPromptTemplate
from requests.packages.urllib3.exceptions import InsecureRequestWarning

os.environ["ANTHROPIC_API_KEY"] = \
  "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"

# Suppress the InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

proxy_address = \
  'brd-customer-hl_9bf54d6c-zone-residential_proxy1:snrfins92iwg@brd.superproxy.io:33335'

proxies = {
    'http': proxy_address,
    'https': proxy_address
}

url_to_access = 'https://mtp.indianrailways.gov.in/view_section.jsp?lang=0&id=0,4,268'

data_file = 'ridership.csv'

def is_valid_date_format(date_string):
  date_format_string = '%d-%m-%Y'
  try:
    datetime.strptime(date_string, date_format_string)
    return True
  except ValueError:
    return False

try:
    # The 'requests' library will route this request through the specified proxy
    response = requests.get(url_to_access, proxies=proxies, timeout=10, verify=False)
    print(f"Successfully accessed site with status code: {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')
        
    # Compile the regex pattern
    regex_pattern = \
      r'\s+(?:\d+\.?\d*)\s+LAKH PASSENGERS (TRAVELED|CARRIED|TRAVELLED) IN METRO'
    link_regex = re.compile(regex_pattern)

    # Find the first <a> tag whose 'href' attribute matches the regex
    matching_link = None
    for link in soup.find_all('a', href=True): # Iterate <a> tags with an href
      match = link_regex.search(link.text)
      if match:
        matching_link = link
        print(f"Matching link: {link.text}")
        break # Stop after finding the first match

    if not matching_link:
        print(f"No link found matching the pattern: {regex_pattern}")

    absolute_link_url = \
      requests.compat.urljoin(url_to_access, matching_link['href'])
    print(f"Found and following link: {absolute_link_url}")

    # Get the data associated with the link
    data_response = \
      requests.get(absolute_link_url, proxies=proxies, timeout=10, verify=False)
    loader = WebBaseLoader(absolute_link_url)
    # Set multiple requests parameters at once
    loader.requests_kwargs = {
        'proxies': proxies,
        'timeout': 30,
        'verify': False,
    }

    # Load the data using WebBasedLoader into a set of docs
    docs = loader.load()

    # Invoke the ChatAnthropic Model
    model = ChatAnthropic(model="claude-3-5-sonnet-20240620")
    prompt = ChatPromptTemplate.from_template("Find out specific dates and" +
    " the number of people who travelled on the metro as well as on" +
    " the Blue Line, Green Line, Yellow Line, Orange Line and Purple Line" +
    " on that date. Return the data in CSV format. If the data is" +
    " not available for a line,leave it as blank. Only print the line with" +
    " data with no headers. The date must be in %d-%m-%Y format. " +
    " \\n\\n{context}")
    chain = prompt | model

    result = chain.invoke({"context": docs})
    print(result.content)

    # Make sure that date is not there in the csv file
    current_date = result.content.split(',')[0]
    if is_valid_date_format(current_date):
      latest_date = ""
      with open(data_file, 'r') as rfile:
        for line in rfile:
          # Assume that ridership.csv is in the correct format
          # and has at least one line
          latest_date = line.split(',')[0]

      print(f"Current date: {current_date}")
      print(f"Latest date: {latest_date}")

      if current_date != latest_date:
        with open(data_file, 'a') as wfile:
          # Write the string followed by a newline character
          wfile.write(result.content + '\n')
          print(f"Successfully appended '{result.content}' to '{data_file}'.")
except requests.exceptions.ProxyError as e:
    print(f"Proxy connection failed: {e}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except IOError as e:
    print(f"I/O Error to file: {e}")
