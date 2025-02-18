import json
import requests
import patoolib
import os
from pprint import pprint
from bs4 import BeautifulSoup
from .Livery import DCSUserFile
from .UnitConfig import Units
from .Utilities import correct_dcs_user_files_url

class DCSUFParserConfig():
  def __init__(self):
    self.DCSUFDivConfig = {}
    self.load_config()

  def load_config(self):
    self.DCSUFDivConfig = self.default_div_config()
    self.load_config_file()

  def default_div_config(self):
    defaultDivConfig = {
      'filetype': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div.row.file-data-1 > div.col-xs-3.type > a",
      'download': "btn btn-primary download",
      'unit': ["body > div.container > div.row.well > div.row.file-head.file-type-skn > div:nth-child(2) > span",
               "body > div.container > div.row.well > div.row.file-head.file-type-skin > div:nth-child(2) > span"],
      'author': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div.row.file-data-1 > div.col-xs-3.author > a",
      'title': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div:nth-child(1) > div > h2",
      'date': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div.row.file-data-1 > div.col-xs-3.date",
      'size': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div.row.file-data-2 > ul > li:nth-child(3)",
      'tags': "body > div.container > div.row.well > div.row.file-body > div.col-xs-10 > div:nth-child(5)"
    }
    return defaultDivConfig

  def load_config_file(self):
    configPath = os.path.join(os.getcwd(), "DCSLM")
    configFilepath = os.path.join(configPath, "dcsuf_parse.json")
    if os.path.isfile(configFilepath):
      try:
        with open(configFilepath, "r") as configFile:
          configData = json.load(configFile)
          for id, v in configData.items():
            if id in self.DCSUFDivConfig.keys():
              self.DCSUFDivConfig[id] = v
          print("loaded custom dcsuf parser config")
          return True
      except:
        raise RuntimeError("Unable to open existing DCSUF Parser config file at \'" + configFilepath + "\'")
    return False

  def write_config(self):
    writePath = os.path.join(os.getcwd(), "DCSLM")
    writeFilepath = os.path.join(writePath, "dcsuf_parse.json")
    try:
      with open(writeFilepath, "w") as writeFile:
        json.dump(self.DCSUFDivConfig, writeFile, indent=2)
        return writeFilepath
    except:
      raise RuntimeError("Failed to write " + writeFilepath)

DCSUFPC = DCSUFParserConfig()

class DCSUFParser():
  def __init__(self):
    self.DCSDownloadUrlPrefix = "https://www.digitalcombatsimulator.com"
    return

  def _get_aircraft_config_from_name(self, aircraftText):
    global AircraftConfigs
    lowerAircraftText = str.lower(aircraftText)
    for aircraft, config in Units.Units['aircraft'].items():
      if lowerAircraftText == str.lower(config['dcs_files']):
        return aircraft, config
      for n in config['names']:
        if str.lower(n) == lowerAircraftText:
          return aircraft, config
    return None, None

  def _remove_bad_filename_characters(self, filename):
    badFilenameCharacters = ['/', '\\', '?', '|', '*', '\"', '<', '>', ':']
    correctFilename = filename
    for c in badFilenameCharacters:
      correctFilename = correctFilename.replace(c, '')
    return " ".join(correctFilename.split()) # Remove extra spaces

  def _get_dcsfiles_archive_url_from_html(self, parsedHTML):
    downloadClass = parsedHTML.find(class_=DCSUFPC.DCSUFDivConfig['download'])
    if downloadClass:
      fullArchiveUrl = self.DCSDownloadUrlPrefix + downloadClass['href']
      archiveType = str.split(fullArchiveUrl, '.')[-1]
      if archiveType in patoolib.ArchiveFormats:
        return fullArchiveUrl
      else:
        raise RuntimeError(fullArchiveUrl + " is not a valid url to an archive file.")

  def make_request_session(self):
    return requests.Session()

  def _request_html_from_url(self, url, session=None):
    try:
      if session:
        r = session.get(url)
      else:
        r = requests.get(url)
      dcsufHTML = BeautifulSoup(r.text, 'html.parser')
      return dcsufHTML
    except:
      raise RuntimeError("Unable to request html from url " + url)

  def _parse_html_for_dcsuf(self, url, dcsufHTML):
    try:
      dcsuf = DCSUserFile()
      fileType = dcsufHTML.select_one(DCSUFPC.DCSUFDivConfig['filetype']).text
      if fileType == "Skin":
        fileURL = self._get_dcsfiles_archive_url_from_html(dcsufHTML)
        if fileURL:
          parsedDCSUF = {}
          for v, d in DCSUFPC.DCSUFDivConfig.items():
            if v == 'filetype' or v == 'download':
              continue
            parsedVar = None
            if isinstance(d, str):
              parsedVar = dcsufHTML.select_one(d)
            elif isinstance(d, list):
              for e in d:
                parsedVar = dcsufHTML.select_one(e)
                if parsedVar:
                  break
            parsedDCSUF[v] = parsedVar
          unitText = parsedDCSUF['unit'].text
          unitGeneric, unitConfig = self._get_aircraft_config_from_name(unitText)
          dcsuf.id = dcsuf.get_id_from_url(url)
          dcsuf.unit = unitGeneric
          dcsuf.author = parsedDCSUF['author'].text
          titleText = parsedDCSUF['title'].text
          dcsuf.title = self._remove_bad_filename_characters(titleText)
          dateText = parsedDCSUF['date'].text
          dateText = str.strip(dateText)
          dateText = dateText[dateText.find('-') + 2:]
          dcsuf.date = dateText
          dcsuf.datetime = dcsuf.date_to_datetime(dcsuf.date)
          dcsuf.size = parsedDCSUF['size'].contents[-1].strip()
          dcsuf.download = fileURL
          if parsedDCSUF['tags'].text.find("Tags:") != -1:
            tagStart = parsedDCSUF['tags'].text.find("Tags:") + 6
            splitTags = parsedDCSUF['tags'].text[tagStart:].split(',')
            for i in range(0, len(splitTags)):
              splitTags[i] = splitTags[i].strip()
            dcsuf.tags = splitTags
          else:
            dcsuf.tags = []
          return dcsuf
      else:
        raise RuntimeError("Provided DCS User files url is not a livery skin file.")
    except:
      raise RuntimeError("Unable to parse html from " + url)

  def get_dcsuserfile_from_url(self, url, session=None):
    correctedURL, id = correct_dcs_user_files_url(url)
    if len(correctedURL):
      dcsuf = None
      try:
        dcsufHTML = self._request_html_from_url(correctedURL, session)
        dcsuf = self._parse_html_for_dcsuf(correctedURL, dcsufHTML)
        return dcsuf
      except Exception as e:
        dcsuf = None
      finally:
        return dcsuf
    return None
