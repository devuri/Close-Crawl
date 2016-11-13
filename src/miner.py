"""scrape_content.py


"""

from csv import DictWriter
from os import path, walk
from re import compile
from re import IGNORECASE
from string import punctuation

from bs4 import BeautifulSoup
from tqdm import trange

from settings import HTML_DIR, HTML_FILE
from settings import FEATURES, FIELDS, INTERNAL_FIELDS

features = [i + ':' for i in FEATURES]
TITLE_SPLIT_PAT = compile(" vs ", IGNORECASE)
ADDR_PAT = compile("(.Balto.)", IGNORECASE)
ZIP_PAT = compile("\d{5}")
# regex pattern to capture monetary values between $0.00 and $999,999,999.99
# punctuation insensitive
MONEY_PAT = compile('\$\d{,3},?\d{,3},?\d{,3}\.?\d{2}')


street_address = compile(
    '(\d{1,4} [\w\s]{1,20}'
    '(?:st(reet)?|ln|lane|ave(nue)?|r(?:oa)?d'
    '|highway|hwy|sq(uare)?|tr(?:ai)l|dr(?:ive)?'
    '|c(?:our)?t|parkway|pkwy|cir(cle)?'
    '|boulevard|blvd|pl(?:ace)?|'
    'ter(?:race)?)\W?(?=\s|$))', IGNORECASE)

punctuation.replace('#', '')


def clean_addr(address):

    try:
        return ''.join(
            street_address.search(
                address.translate(None, punctuation)).group(0)
        )

    except AttributeError:

        return ''


def scrape(case_type, html_data):
    """Scrapes the desired features

    input:
      html_data: <str>, source HTML

    output:
      scraped_features: <dict>, features scraped and mapped from content
    """

    soup = BeautifulSoup(html_data, "html.parser")
    td_list = soup.find_all("tr")

    if any(x in str(soup.h5).upper()
           for x in ["CASE INFORMATION", "DEFENDANT"]):

        feature_list = []
        for tag in td_list:
            try:
                tag = [j.string for j in tag.findAll("span")]
                if set(tuple(tag)) & set(features):
                    try:
                        tag = [i for i in tag if "(each" not in i.lower()]
                    except AttributeError:
                        continue
                    feature_list.append(tag)

            except IndexError:
                continue

        try:
            # flatten multidimensional list
            feature_list = [item.replace(':', '')
                            for sublist in feature_list for item in sublist]

        except Exception as e:
            print e, feature_list

        return distribute(feature_list)


def distribute(feature_list):

    # break up elements with n-tuples greater than 2
    # then convert list of tuples to dict for faster lookup
    business = [
        tuple(feature_list[i:i + 2])
        for i in xrange(0, len(feature_list), 2)
        if any(x in feature_list[i:i + 2][0] for x in INTERNAL_FIELDS)
    ]

    feature_list = dict([
        tuple(feature_list[i:i + 2])
        for i in xrange(0, len(feature_list), 2)
        if feature_list[i:i + 2][0] in FEATURES
    ])

    filt = []

    for ii in xrange(len(business)):
        try:
            if business[ii][1].upper() == "PROPERTY ADDRESS" and \
                    business[ii + 1][0].upper() == "BUSINESS OR ORGANIZATION NAME":
                filt.append(business[ii + 1])

        except IndexError:
            print "Party Type issue at Case", feature_list["Case Number"]

    business = filt
    scraped_features = []
    temp_features = {}

    for address in business:

        str_address = clean_addr(str(address[-1]))

        temp_features["Title"] = feature_list["Title"]
        temp_features["Case Type"] = feature_list["Case Type"]
        temp_features["Case Number"] = feature_list["Case Number"]
        temp_features["Filing Date"] = feature_list["Filing Date"]

        # break up Title feature into Plaintiff and Defendant
        try:
            temp_features["Plaintiff"], temp_features["Defendant"] = \
                TITLE_SPLIT_PAT.split(temp_features["Title"])

        except ValueError:
            temp_features["Plaintiff"], temp_features["Defendant"] = \
                ('', '')

        if temp_features["Case Type"].upper() == "FORECLOSURE":
            temp_features["Case Type"] = "Mortgage"

        temp_features["Address"] = str_address if str_address else address[-1]

        temp_features["Zip Code"] = ''.join(
            ZIP_PAT.findall(address[-1])
        )

        temp_features["Partial Cost"] = ''.join(
            MONEY_PAT.findall(address[-1])
        )

        scraped_features.append(temp_features)
        temp_features = {}

    if not scraped_features:
        with open('no_case.txt', 'a') as empty_case:
            empty_case.write(feature_list["Case Number"] + '\n')

    return scraped_features


def export(file_array, out_db, gui=False):

    dataset = []
    file_exists = path.isfile(out_db)

    case_range = trange(len(file_array), desc='Mining', leave=True)

    for file_name in case_range:
        with open(
            HTML_FILE.format(case=file_array[file_name]), 'r'
        ) as html_src:
            row = scrape(file_name, html_src.read())

            if not gui:
                case_range.set_description(
                    "Mining {}".format(file_array[file_name]))

            dataset.extend(row)

    with open(out_db, 'a') as csv_file:
        writer = DictWriter(csv_file, fieldnames=FIELDS)

        if not file_exists:
            writer.writeheader()

        for row in dataset:
            writer.writerow(row)


if __name__ == '__main__':

    # print STREET_ADDR_PAT()
    # print street_address.search('4401 Powell Avenue BaltimoreMD 2120627087300'.translate(None, punctuation)).group(0)
    # print STREET_ADDR_PAT1 == STREET_ADDR_PAT()

    file_array = sorted([filenames for (dirpath, dirnames, filenames)
                         in walk(HTML_DIR)][0])

    out_db = 'test_out.csv'
    export(file_array, out_db)
