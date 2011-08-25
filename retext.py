#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=8:noexpandtab

# ReText
# Copyright 2011 Dmitry Shachnev

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import sys
import subprocess
from PyQt4.QtCore import *
from PyQt4.QtGui import *

app_name = "ReText"
app_version = "2.0.0"

s = QSettings('ReText project', 'ReText')

try:
	import markdown
except:
	use_md = False
else:
	use_md = True
	if s.contains('mdExtensions'):
		exts = []
		for ext in s.value('mdExtensions').toStringList():
			exts.append(str(ext))
		md = markdown.Markdown(exts)
	else:
		md = markdown.Markdown()

try:
	import gdata.docs
	import gdata.docs.service
	from gdata import MediaSource
except:
	use_gdocs = False
else:
	use_gdocs = True

try:
	import enchant
except:
	use_enchant = False
else:
	use_enchant = True

dictionary = None

try:
	from docutils.core import publish_parts
except:
	use_docutils = False
else:
	use_docutils = True

icon_path = "icons/"

PARSER_DOCUTILS, PARSER_MARKDOWN, PARSER_HTML, PARSER_NA = range(4)

if QFileInfo("wpgen/wpgen.py").isExecutable():
	wpgen = unicode(QFileInfo("wpgen/wpgen.py").canonicalFilePath(), 'utf-8')
elif QFileInfo("/usr/bin/wpgen").isExecutable():
	wpgen = "/usr/bin/wpgen"
else:
	wpgen = None

monofont = QFont()
if s.contains('editorFont'):
	monofont.setFamily(s.value('editorFont').toString())
else:
	monofont.setFamily('monospace')
if s.contains('editorFontSize'):
	monofont.setPointSize(s.value('editorFontSize').toInt()[0])

use_webkit = False
if s.contains('useWebKit'):
	if s.value('useWebKit').toBool():
		try:
			from PyQt4.QtWebKit import QWebView
		except:
			pass
		else:
			use_webkit = True

class ReTextHighlighter(QSyntaxHighlighter):
	def __init__(self, parent):
		QSyntaxHighlighter.__init__(self, parent)
	
	def highlightBlock(self, text):
		words = '[\\w][^\\W]*'
		if dictionary:
			text = unicode(text)
			charFormat = QTextCharFormat()
			charFormat.setUnderlineColor(Qt.red)
			charFormat.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
			expression = QRegExp(words)
			index = expression.indexIn(text)
			while (index >= 0):
				length = expression.matchedLength()
				if not dictionary.check(text[index:index+length]):
					self.setFormat(index, length, charFormat)
				index = expression.indexIn(text, index + length)
		charFormat = QTextCharFormat()
		patterns = ('<[^<>]*>', '&[^; ]*;', '"[^"<]*"(?=[^<]*>)', '<!--[^-->]*-->')
		foregrounds = (Qt.darkMagenta, Qt.darkCyan, Qt.darkYellow, Qt.gray)
		for i in range(len(patterns)):
			expression = QRegExp(patterns[i])
			index = expression.indexIn(text)
			if i == 3:
				charFormat.setFontWeight(QFont.Normal)
			else:
				charFormat.setFontWeight(QFont.Bold)
			charFormat.setForeground(foregrounds[i])
			while (index >= 0):
				length = expression.matchedLength()
				self.setFormat(index, length, charFormat)
				index = expression.indexIn(text, index + length)

class LogPassDialog(QDialog):
	def __init__(self, defaultLogin="", defaultPass=""):
		QDialog.__init__(self)
		self.setWindowTitle(app_name)
		self.verticalLayout = QVBoxLayout(self)
		self.label = QLabel(self)
		self.label.setText(self.tr("Enter your Google account data"))
		self.verticalLayout.addWidget(self.label)
		self.loginEdit = QLineEdit(self)
		self.loginEdit.setText(defaultLogin)
		self.verticalLayout.addWidget(self.loginEdit)
		self.passEdit = QLineEdit(self)
		self.passEdit.setText(defaultPass)
		self.passEdit.setEchoMode(QLineEdit.Password)
		try:
			self.loginEdit.setPlaceholderText(self.tr("Username"))
			self.passEdit.setPlaceholderText(self.tr("Password"))
		except:
			pass
		self.verticalLayout.addWidget(self.passEdit)
		self.buttonBox = QDialogButtonBox(self)
		self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
		self.verticalLayout.addWidget(self.buttonBox)
		self.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		self.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)

class HtmlDialog(QDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.resize(600, 500)
		self.verticalLayout = QVBoxLayout(self)
		self.textEdit = QTextEdit(self)
		self.textEdit.setReadOnly(True)
		self.textEdit.setFont(monofont)
		ReTextHighlighter(self.textEdit.document())
		self.verticalLayout.addWidget(self.textEdit)
		self.buttonBox = QDialogButtonBox(self)
		self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
		self.connect(self.buttonBox, SIGNAL("clicked(QAbstractButton*)"), self.doClose)
		self.verticalLayout.addWidget(self.buttonBox)
	
	def doClose(self):
		self.close()

class ReTextWindow(QMainWindow):
	def __init__(self, parent=None):
		QMainWindow.__init__(self, parent)
		self.resize(800, 600)
		screen = QDesktopWidget().screenGeometry()
		size = self.geometry()
		self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)
		settings = QSettings()
		if settings.contains('iconTheme'):
			QIcon.setThemeName(settings.value('iconTheme').toString())
		if settings.contains('font'):
			self.font = QFont(settings.value('font').toString())
			if settings.contains('fontSize'):
				self.font.setPointSize(settings.value('fontSize').toInt()[0])
		else:
			self.font = None
		self.setWindowTitle(self.tr('New document') + '[*] ' + QChar(0x2014) + ' ' + app_name)
		if QFile.exists(icon_path+'retext.png'):
			self.setWindowIcon(QIcon(icon_path+'retext.png'))
		else:
			self.setWindowIcon(QIcon.fromTheme('retext', QIcon.fromTheme('accessories-text-editor')))
		self.editBoxes = []
		self.previewBoxes = []
		self.fileNames = []
		self.apc = []
		self.alpc = []
		self.aptc = []
		self.tabWidget = QTabWidget(self)
		self.tabWidget.setTabsClosable(True)
		self.setCentralWidget(self.tabWidget)
		self.connect(self.tabWidget, SIGNAL('currentChanged(int)'), self.changeIndex)
		self.connect(self.tabWidget, SIGNAL('tabCloseRequested(int)'), self.closeTab)
		self.toolBar = QToolBar(self.tr('File toolbar'), self)
		self.addToolBar(Qt.TopToolBarArea, self.toolBar)
		self.editBar = QToolBar(self.tr('Edit toolbar'), self)
		self.addToolBar(Qt.TopToolBarArea, self.editBar)
		self.searchBar = QToolBar(self.tr('Search toolbar'), self)
		self.addToolBar(Qt.BottomToolBarArea, self.searchBar)
		self.actionNew = QAction(self.actIcon('document-new'), self.tr('New'), self)
		self.actionNew.setShortcut(QKeySequence.New)
		self.actionNew.setPriority(QAction.LowPriority)
		self.connect(self.actionNew, SIGNAL('triggered()'), self.createNew)
		self.actionOpen = QAction(self.actIcon('document-open'), self.tr('Open'), self)
		self.actionOpen.setShortcut(QKeySequence.Open)
		self.actionOpen.setPriority(QAction.LowPriority)
		self.connect(self.actionOpen, SIGNAL('triggered()'), self.openFile)
		self.actionSave = QAction(self.actIcon('document-save'), self.tr('Save'), self)
		self.actionSave.setEnabled(False)
		self.actionSave.setShortcut(QKeySequence.Save)
		self.actionSave.setPriority(QAction.LowPriority)
		self.connect(self.actionSave, SIGNAL('triggered()'), self.saveFile)
		self.actionSaveAs = QAction(self.actIcon('document-save-as'), self.tr('Save as'), self)
		self.actionSaveAs.setShortcut(QKeySequence.SaveAs)
		self.connect(self.actionSaveAs, SIGNAL('triggered()'), self.saveFileAs)
		self.actionPrint = QAction(self.actIcon('document-print'), self.tr('Print'), self)
		self.actionPrint.setShortcut(QKeySequence.Print)
		self.actionPrint.setPriority(QAction.LowPriority)
		self.connect(self.actionPrint, SIGNAL('triggered()'), self.printFile)
		self.actionPrintPreview = QAction(self.actIcon('document-print-preview'), self.tr('Print preview'), self)
		self.connect(self.actionPrintPreview, SIGNAL('triggered()'), self.printPreview)
		self.actionViewHtml = QAction(self.actIcon('text-html'), self.tr('View HTML code'), self)
		self.connect(self.actionViewHtml, SIGNAL('triggered()'), self.viewHtml)
		self.actionChangeFont = QAction(self.tr('Change default font'), self)
		self.connect(self.actionChangeFont, SIGNAL('triggered()'), self.changeFont)
		self.actionSearch = QAction(self.actIcon('edit-find'), self.tr('Find text'), self)
		self.actionSearch.setCheckable(True)
		self.actionSearch.setShortcut(QKeySequence.Find)
		self.connect(self.actionSearch, SIGNAL('triggered(bool)'), self.searchBar, SLOT('setVisible(bool)'))
		self.connect(self.searchBar, SIGNAL('visibilityChanged(bool)'), self.actionSearch, SLOT('setChecked(bool)'))
		self.actionPreview = QAction(self.tr('Preview'), self)
		if QIcon.hasThemeIcon('document-preview'):
			self.actionPreview.setIcon(QIcon.fromTheme('document-preview'))
		elif QIcon.hasThemeIcon('preview-file'):
			self.actionPreview.setIcon(QIcon.fromTheme('preview-file'))
		elif QIcon.hasThemeIcon('x-office-document'):
			self.actionPreview.setIcon(QIcon.fromTheme('x-office-document'))
		else:
			self.actionPreview.setIcon(QIcon(icon_path+'document-preview.png'))
		self.actionPreview.setCheckable(True)
		self.actionPreview.setShortcut(Qt.CTRL + Qt.Key_E)
		self.connect(self.actionPreview, SIGNAL('triggered(bool)'), self.preview)
		self.actionLivePreview = QAction(self.tr('Live preview'), self)
		self.actionLivePreview.setCheckable(True)
		self.actionLivePreview.setShortcut(Qt.CTRL + Qt.SHIFT + Qt.Key_E)
		self.connect(self.actionLivePreview, SIGNAL('triggered(bool)'), self.enableLivePreview)
		self.actionFullScreen = QAction(self.actIcon('view-fullscreen'), self.tr('Fullscreen mode'), self)
		self.actionFullScreen.setCheckable(True)
		self.actionFullScreen.setShortcut(Qt.Key_F11)
		self.connect(self.actionFullScreen, SIGNAL('triggered(bool)'), self.enableFullScreen)
		self.actionPerfectHtml = QAction(self.actIcon('text-html'), 'HTML', self)
		self.connect(self.actionPerfectHtml, SIGNAL('triggered()'), self.saveFilePerfect)
		self.actionPdf = QAction(self.actIcon('application-pdf'), 'PDF', self)
		self.connect(self.actionPdf, SIGNAL('triggered()'), self.savePdf)
		self.actionOdf = QAction(self.actIcon('x-office-document'), 'ODT', self)
		self.connect(self.actionOdf, SIGNAL('triggered()'), self.saveOdf)
		settings.beginGroup('Export')
		if not settings.allKeys().isEmpty():
			self.actionOtherExport = QAction(self.tr('Other formats'), self)
			self.connect(self.actionOtherExport, SIGNAL('triggered()'), self.otherExport)
			otherExport = True
		else:
			otherExport = False
		settings.endGroup()
		self.actionQuit = QAction(self.actIcon('application-exit'), self.tr('Quit'), self)
		self.actionQuit.setShortcut(QKeySequence.Quit)
		self.actionQuit.setMenuRole(QAction.QuitRole)
		self.connect(self.actionQuit, SIGNAL('triggered()'), qApp, SLOT('quit()'))
		self.actionUndo = QAction(self.actIcon('edit-undo'), self.tr('Undo'), self)
		self.actionUndo.setShortcut(QKeySequence.Undo)
		self.actionRedo = QAction(self.actIcon('edit-redo'), self.tr('Redo'), self)
		self.actionRedo.setShortcut(QKeySequence.Redo)
		self.actionUndo.setEnabled(False)
		self.actionRedo.setEnabled(False)
		self.actionCopy = QAction(self.actIcon('edit-copy'), self.tr('Copy'), self)
		self.actionCopy.setShortcut(QKeySequence.Copy)
		self.actionCopy.setEnabled(False)
		self.actionCut = QAction(self.actIcon('edit-cut'), self.tr('Cut'), self)
		self.actionCut.setShortcut(QKeySequence.Cut)
		self.actionCut.setEnabled(False)
		self.actionPaste = QAction(self.actIcon('edit-paste'), self.tr('Paste'), self)
		self.actionPaste.setShortcut(QKeySequence.Paste)
		self.connect(self.actionUndo, SIGNAL('triggered()'), \
		lambda: self.editBoxes[self.ind].undo())
		self.connect(self.actionRedo, SIGNAL('triggered()'), \
		lambda: self.editBoxes[self.ind].redo())
		self.connect(self.actionCut, SIGNAL('triggered()'), \
		lambda: self.editBoxes[self.ind].cut())
		self.connect(self.actionCopy, SIGNAL('triggered()'), \
		lambda: self.editBoxes[self.ind].copy())
		self.connect(self.actionPaste, SIGNAL('triggered()'), \
		lambda: self.editBoxes[self.ind].paste())
		self.connect(qApp.clipboard(), SIGNAL('dataChanged()'), self.clipboardDataChanged)
		self.clipboardDataChanged()
		self.sc = False
		if use_enchant:
			self.actionEnableSC = QAction(self.tr('Enable'), self)
			self.actionEnableSC.setCheckable(True)
			self.actionSetLocale = QAction(self.tr('Set locale'), self)
			self.connect(self.actionEnableSC, SIGNAL('triggered(bool)'), self.enableSC)
			self.connect(self.actionSetLocale, SIGNAL('triggered()'), self.changeLocale)
			if settings.contains('spellCheckLocale'):
				self.sl = str(settings.value('spellCheckLocale').toString())
			else:
				self.sl = None
			if settings.contains('spellCheck'):
				if settings.value('spellCheck').toBool():
					self.actionEnableSC.setChecked(True)
					self.enableSC(True)
		self.actionPlainText = QAction(self.tr('Plain text'), self)
		self.actionPlainText.setCheckable(True)
		self.connect(self.actionPlainText, SIGNAL('triggered(bool)'), self.enablePlainText)
		self.actionRecentFiles = QAction(self.actIcon('document-open-recent'), self.tr('Open recent'), self)
		self.connect(self.actionRecentFiles, SIGNAL('triggered()'), self.openRecent)
		if wpgen:
			self.actionWpgen = QAction(self.tr('Generate webpages'), self)
			self.connect(self.actionWpgen, SIGNAL('triggered()'), self.startWpgen)
		self.actionShow = QAction(self.actIcon('system-file-manager'), self.tr('Show'), self)
		self.connect(self.actionShow, SIGNAL('triggered()'), self.showInDir)
		self.actionFind = QAction(self.actIcon('go-next'), self.tr('Next'), self)
		self.actionFind.setShortcut(QKeySequence.FindNext)
		self.actionFindPrev = QAction(self.actIcon('go-previous'), self.tr('Previous'), self)
		self.actionFindPrev.setShortcut(QKeySequence.FindPrevious)
		self.connect(self.actionFind, SIGNAL('triggered()'), self.find)
		self.connect(self.actionFindPrev, SIGNAL('triggered()'), lambda: self.find(QTextDocument.FindBackward))
		self.actionAbout = QAction(self.actIcon('help-about'), self.tr('About %1').arg(app_name), self)
		self.actionAbout.setMenuRole(QAction.AboutRole)
		self.connect(self.actionAbout, SIGNAL('triggered()'), self.aboutDialog)
		self.actionAboutQt = QAction(self.tr('About Qt'), self)
		self.actionAboutQt.setMenuRole(QAction.AboutQtRole)
		self.chooseGroup = QActionGroup(self)
		self.useDocUtils = False
		self.actionUseMarkdown = QAction('Markdown', self)
		self.actionUseMarkdown.setCheckable(True)
		self.actionUseReST = QAction('ReStructuredText', self)
		self.actionUseReST.setCheckable(True)
		if settings.contains('useReST'):
			if settings.value('useReST').toBool():
				if use_docutils:
					self.useDocUtils = True
				self.actionUseReST.setChecked(True)
			else:
				self.actionUseMarkdown.setChecked(True)
		else:
			self.actionUseMarkdown.setChecked(True)
		self.connect(self.actionUseReST, SIGNAL('toggled(bool)'), self.setDocUtilsDefault)
		self.chooseGroup.addAction(self.actionUseMarkdown)
		self.chooseGroup.addAction(self.actionUseReST)
		if use_gdocs:
			self.actionSaveGDocs = QAction(QIcon.fromTheme('web-browser', self.actIcon('intenret-web-browser')), self.tr('Save to Google Docs'), self)
			self.connect(self.actionSaveGDocs, SIGNAL('triggered()'), self.saveGDocs)
		self.connect(self.actionAboutQt, SIGNAL('triggered()'), qApp, SLOT('aboutQt()'))
		self.usefulTags = ('center', 's', 'span', 'table', 'td', 'tr', 'u')
		self.usefulChars = ('deg', 'divide', 'hellip', 'laquo', 'larr', 'mdash', 'middot', 'minus', 'nbsp', 'ndash', 'raquo', 'rarr', 'times')
		self.tagsBox = QComboBox(self.editBar)
		self.tagsBox.addItem(self.tr('Tags'))
		self.tagsBox.addItems(self.usefulTags)
		self.connect(self.tagsBox, SIGNAL('activated(int)'), self.insertTag)
		self.symbolBox = QComboBox(self.editBar)
		self.symbolBox.addItem(self.tr('Symbols'))
		self.symbolBox.addItems(self.usefulChars)
		self.connect(self.symbolBox, SIGNAL('activated(int)'), self.insertSymbol)
		if settings.contains('styleSheet'):
			self.ssname = settings.value('styleSheet').toString()
			sheetfile = QFile(self.ssname)
			sheetfile.open(QIODevice.ReadOnly)
			self.ss = QTextStream(sheetfile).readAll()
			sheetfile.close()
		else:
			self.ss = ''
		self.menubar = QMenuBar(self)
		self.menubar.setGeometry(QRect(0, 0, 800, 25))
		self.setMenuBar(self.menubar)
		self.menuFile = self.menubar.addMenu(self.tr('File'))
		self.menuEdit = self.menubar.addMenu(self.tr('Edit'))
		self.menuHelp = self.menubar.addMenu(self.tr('Help'))
		self.menuFile.addAction(self.actionNew)
		self.menuFile.addAction(self.actionOpen)
		self.menuFile.addAction(self.actionRecentFiles)
		self.menuDir = self.menuFile.addMenu(self.tr('Directory'))
		self.menuDir.addAction(self.actionShow)
		if wpgen:
			self.menuDir.addAction(self.actionWpgen)
		self.menuFile.addSeparator()
		self.menuFile.addAction(self.actionSave)
		self.menuFile.addAction(self.actionSaveAs)
		self.menuFile.addSeparator()
		self.menuExport = self.menuFile.addMenu(self.tr('Export'))
		self.menuExport.addAction(self.actionPerfectHtml)
		self.menuExport.addAction(self.actionOdf)
		self.menuExport.addAction(self.actionPdf)
		if otherExport:
			self.menuExport.addAction(self.actionOtherExport)
		if use_gdocs:
			self.menuExport.addSeparator()
			self.menuExport.addAction(self.actionSaveGDocs)
		self.menuFile.addAction(self.actionPrint)
		self.menuFile.addAction(self.actionPrintPreview)
		self.menuFile.addSeparator()
		self.menuFile.addAction(self.actionQuit)
		self.menuEdit.addAction(self.actionUndo)
		self.menuEdit.addAction(self.actionRedo)
		self.menuEdit.addSeparator()
		self.menuEdit.addAction(self.actionCut)
		self.menuEdit.addAction(self.actionCopy)
		self.menuEdit.addAction(self.actionPaste)
		self.menuEdit.addSeparator()
		if use_enchant:
			self.menuSC = self.menuEdit.addMenu(self.tr('Spell check'))
			self.menuSC.addAction(self.actionEnableSC)
			self.menuSC.addAction(self.actionSetLocale)
		self.menuEdit.addAction(self.actionSearch)
		self.menuEdit.addAction(self.actionPlainText)
		self.menuEdit.addAction(self.actionChangeFont)
		self.menuEdit.addSeparator()
		if use_docutils and use_md:
			self.menuMode = self.menuEdit.addMenu(self.tr('Default editing mode'))
			self.menuMode.addAction(self.actionUseMarkdown)
			self.menuMode.addAction(self.actionUseReST)
			self.menuEdit.addSeparator()
		self.menuEdit.addAction(self.actionViewHtml)
		self.menuEdit.addAction(self.actionLivePreview)
		self.menuEdit.addAction(self.actionPreview)
		self.menuEdit.addSeparator()
		self.menuEdit.addAction(self.actionFullScreen)
		self.menuHelp.addAction(self.actionAbout)
		self.menuHelp.addAction(self.actionAboutQt)
		self.menubar.addMenu(self.menuFile)
		self.menubar.addMenu(self.menuEdit)
		self.menubar.addMenu(self.menuHelp)
		self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
		self.toolBar.addAction(self.actionNew)
		self.toolBar.addSeparator()
		self.toolBar.addAction(self.actionOpen)
		self.toolBar.addAction(self.actionSave)
		self.toolBar.addAction(self.actionPrint)
		self.toolBar.addSeparator()
		self.toolBar.addAction(self.actionPreview)
		self.editBar.addAction(self.actionUndo)
		self.editBar.addAction(self.actionRedo)
		self.editBar.addSeparator()
		self.editBar.addAction(self.actionCut)
		self.editBar.addAction(self.actionCopy)
		self.editBar.addAction(self.actionPaste)
		self.editBar.addSeparator()
		self.editBar.addWidget(self.tagsBox)
		self.editBar.addWidget(self.symbolBox)
		self.searchEdit = QLineEdit(self.searchBar)
		try:
			self.searchEdit.setPlaceholderText(self.tr('Search'))
		except:
			pass
		self.connect(self.searchEdit, SIGNAL('returnPressed()'), self.find)
		self.csBox = QCheckBox(self.tr('Case sensitively'), self.searchBar)
		self.searchBar.addWidget(self.searchEdit)
		self.searchBar.addWidget(self.csBox)
		self.searchBar.addAction(self.actionFindPrev)
		self.searchBar.addAction(self.actionFind)
		self.searchBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
		self.searchBar.setVisible(False)
		self.autoSave = False
		if settings.contains('autoSave'):
			if settings.value('autoSave').toBool():
				self.autoSave = True
				timer = QTimer(self)
				timer.start(5000)
				self.connect(timer, SIGNAL('timeout()'), self.saveAll)
		self.ind = 0
		self.tabWidget.addTab(self.createTab(""), self.tr('New document'))
		if not (use_md or use_docutils):
			QMessageBox.warning(self, app_name, self.tr('You have neither Markdown nor Docutils modules installed!') \
			+'<br>'+self.tr('Only HTML formatting will be available.'))
	
	def actIcon(self, name):
		return QIcon.fromTheme(name, QIcon(icon_path+name+'.png'))
	
	def createTab(self, fileName):
		self.editBoxes.append(QTextEdit())
		ReTextHighlighter(self.editBoxes[-1].document())
		s = QSettings()
		if use_webkit:
			self.previewBoxes.append(QWebView())
			self.previewBoxes[-1].setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		else:
			self.previewBoxes.append(QTextEdit())
			self.previewBoxes[-1].setReadOnly(True)
		self.previewBoxes[-1].setVisible(False)
		self.fileNames.append(fileName)
		self.apc.append(False)
		self.alpc.append(False)
		self.aptc.append(False)
		self.editBoxes[-1].setFont(monofont)
		self.editBoxes[-1].setAcceptRichText(False)
		self.connect(self.editBoxes[-1], SIGNAL('textChanged()'), self.updateLivePreviewBox)
		self.connect(self.editBoxes[-1], SIGNAL('undoAvailable(bool)'), self.actionUndo, SLOT('setEnabled(bool)'))
		self.connect(self.editBoxes[-1], SIGNAL('redoAvailable(bool)'), self.actionRedo, SLOT('setEnabled(bool)'))
		self.connect(self.editBoxes[-1], SIGNAL('copyAvailable(bool)'), self.enableCopy)
		self.connect(self.editBoxes[-1].document(), SIGNAL('modificationChanged(bool)'), self.modificationChanged)
		tab = QWidget()
		layout = QHBoxLayout(tab)
		layout.addWidget(self.editBoxes[-1])
		layout.addWidget(self.previewBoxes[-1])
		return tab
	
	def closeTab(self, ind):
		if self.maybeSave(ind):
			if self.tabWidget.count() == 1:
				self.tabWidget.addTab(self.createTab(""), self.tr("New document"))
			del self.editBoxes[ind]
			del self.previewBoxes[ind]
			del self.fileNames[ind]
			del self.apc[ind]
			del self.alpc[ind]
			del self.aptc[ind]
			self.tabWidget.removeTab(ind)
	
	def changeIndex(self, ind):
		if ind > -1:
			self.actionPlainText.setChecked(self.aptc[ind])
			self.enablePlainTextMain(self.aptc[ind])
			self.actionUndo.setEnabled(self.editBoxes[ind].document().isUndoAvailable())
			self.actionRedo.setEnabled(self.editBoxes[ind].document().isRedoAvailable())
			self.actionCopy.setEnabled(self.editBoxes[ind].textCursor().hasSelection())
			self.actionCut.setEnabled(self.editBoxes[ind].textCursor().hasSelection())
			self.actionPreview.setChecked(self.apc[ind])
			self.actionLivePreview.setChecked(self.alpc[ind])
			self.editBar.setDisabled(self.apc[ind])
		self.ind = ind
		if self.fileNames[ind]:
			self.setWindowTitle("")
			self.setWindowFilePath(self.fileNames[ind])
		else:
			self.setWindowTitle(self.tr('New document') + '[*] ' + QChar(0x2014) + ' ' + app_name)
		self.modificationChanged(self.editBoxes[ind].document().isModified())
		self.editBoxes[self.ind].setFocus(Qt.OtherFocusReason)
	
	def changeFont(self):
		if not self.font:
			self.font = QFont()
		fd = QFontDialog.getFont(self.font, self)
		if fd[1]:
			self.font = QFont()
			self.font.setFamily(fd[0].family())
			QSettings().setValue('font', fd[0].family())
			self.font.setPointSize(fd[0].pointSize())
			QSettings().setValue('fontSize', fd[0].pointSize())
			self.updatePreviewBox()
	
	def preview(self, viewmode):
		self.apc[self.ind] = viewmode
		if self.actionLivePreview.isChecked:
			self.actionLivePreview.setChecked(False)
		self.editBar.setDisabled(viewmode)
		self.editBoxes[self.ind].setVisible(not viewmode)
		self.previewBoxes[self.ind].setVisible(viewmode)
		if viewmode:
			self.updatePreviewBox()
	
	def enableLivePreview(self, livemode):
		self.alpc[self.ind] = livemode
		self.actionPreview.setChecked(livemode)
		self.editBar.setEnabled(True)
		self.previewBoxes[self.ind].setVisible(livemode)
		self.editBoxes[self.ind].setVisible(True)
		if livemode:
			self.updatePreviewBox()
	
	def enableCopy(self, copymode):
		self.actionCopy.setEnabled(copymode)
		self.actionCut.setEnabled(copymode)
	
	def enableFullScreen(self, yes):
		if yes:
			self.showFullScreen()
		else:
			self.showNormal()
	
	def keyPressEvent(self, e):
		v = not self.menubar.isVisible()
		if e.key() == Qt.Key_F12 and e.modifiers() & Qt.ShiftModifier:
			self.menubar.setVisible(v)
			self.toolBar.setVisible(v)
			self.editBar.setVisible(v)
		elif e.key() == Qt.Key_F11:
			if v:
				n = not self.actionFullScreen.isChecked()
				self.actionFullScreen.setChecked(n)
				self.enableFullScreen(n)
	
	def enableSC(self, yes):
		global dictionary
		if yes:
			if self.sl:
				dictionary = enchant.Dict(self.sl)
			else:
				dictionary = enchant.Dict()
			QSettings().setValue('spellCheck', True)
		else:
			dictionary = None
			QSettings().remove('spellCheck')
	
	def changeLocale(self):
		if self.sl == None:
			text = ""
		else:
			text = self.sl
		sl, ok = QInputDialog.getText(self, app_name, self.tr('Enter locale name (example: en_US)'), QLineEdit.Normal, text)
		if ok and sl:
			try:
				sl = str(sl)
			except:
				pass
			else:
				self.sl = sl
				self.enableSC(self.actionEnableSC.isChecked())
		elif sl.isEmpty():
			self.sl = None
			self.enableSC(self.actionEnableSC.isChecked())
	
	def find(self, back=False):
		flags = 0
		if back:
			flags = flags | QTextDocument.FindBackward
		if self.csBox.isChecked():
			flags = flags | QTextDocument.FindCaseSensitively
		text = self.searchEdit.text()
		if not self.findMain(text, flags):
			if text in self.editBoxes[self.ind].toPlainText():
				cursor = self.editBoxes[self.ind].textCursor()
				if back:
					cursor.movePosition(QTextCursor.End)
				else:
					cursor.movePosition(QTextCursor.Start)
				self.editBoxes[self.ind].setTextCursor(cursor)
				self.findMain(text, flags)
	
	def findMain(self, text, flags):
		if flags:
			return self.editBoxes[self.ind].find(text, flags)
		else:
			return self.editBoxes[self.ind].find(text)
	
	def updatePreviewBox(self):
		self.previewBlocked = False
		pb = self.previewBoxes[self.ind]
		if self.ss:
			if use_webkit:
				pb.settings().setUserStyleSheetUrl(QUrl.fromLocalFile(self.ssname))
			else:
				pb.document().setDefaultStyleSheet(self.ss)
		if self.actionPlainText.isChecked():
			if use_webkit:
				td = QTextDocument()
				td.setPlainText(self.editBoxes[self.ind].toPlainText())
				pb.setHtml(td.toHtml())
			else:
				pb.setPlainText(self.editBoxes[self.ind].toPlainText())
		else:
			pb.setHtml(self.parseText())
		if self.font and not use_webkit:
			pb.document().setDefaultFont(self.font)
	
	def updateLivePreviewBox(self):
		if self.actionLivePreview.isChecked() and self.previewBlocked == False:
			self.previewBlocked = True
			QTimer.singleShot(1000, self.updatePreviewBox)
	
	def startWpgen(self):
		if self.fileNames[self.ind] == "":
			QMessageBox.warning(self, app_name, self.tr("Please, save the file somewhere."))
		elif wpgen:
			if not (QDir("html").exists() and QFile.exists("template.html")):
				subprocess.Popen([wpgen, 'init']).wait()
			subprocess.Popen([wpgen, 'updateall']).wait()
			QMessageBox.information(self, app_name, self.tr("Webpages saved in <code>html</code> directory."))
	
	def showInDir(self):
		if self.fileNames[self.ind]:
			QDesktopServices.openUrl(QUrl.fromLocalFile(QFileInfo(self.fileNames[self.ind]).path()))
		else:
			QMessageBox.warning(self, app_name, self.tr("Please, save the file somewhere."))
	
	def setCurrentFile(self):
		self.setWindowTitle("")
		self.tabWidget.setTabText(self.ind, self.getDocumentTitle(baseName=True))
		self.setWindowFilePath(self.fileNames[self.ind])
		settings = QSettings()
		files = settings.value("recentFileList").toStringList()
		files.prepend(self.fileNames[self.ind])
		files.removeDuplicates()
		if len(files) > 10:
			del files[10:]
		settings.setValue("recentFileList", files)
		QDir.setCurrent(QFileInfo(self.fileNames[self.ind]).dir().path())
	
	def createNew(self):
		self.tabWidget.addTab(self.createTab(""), self.tr("New document"))
		self.ind = self.tabWidget.count()-1
		self.tabWidget.setCurrentIndex(self.ind)
	
	def openRecent(self):
		filesOld = QSettings().value("recentFileList").toStringList()
		files = QStringList()
		for i in filesOld:
			if QFile.exists(i):
				files.append(i)
		QSettings().setValue("recentFileList", files)
		item, ok = QInputDialog.getItem(self, app_name, self.tr("Open recent"), files, 0, False)
		if ok and not item.isEmpty():
			self.openFileWrapper(item)
	
	def openFile(self):
		fileName = QFileDialog.getOpenFileName(self, self.tr("Open file"), "", \
		self.tr("Supported files")+" (*.re *.md *.markdown *.mdown *.mkd *.mkdn *.rst *.rest *.txt *.html *.htm);;"+self.tr("All files (*)"))
		self.openFileWrapper(fileName)
	
	def openFileWrapper(self, fileName):
		if fileName:
			exists = False
			for i in range(self.tabWidget.count()):
				if self.fileNames[i] == fileName:
					exists = True
					ex = i
			if exists:
				self.tabWidget.setCurrentIndex(ex)
			else:
				if self.fileNames[self.ind] or self.editBoxes[self.ind].toPlainText() or self.editBoxes[self.ind].document().isModified():
					self.tabWidget.addTab(self.createTab(""), "")
					self.ind = self.tabWidget.count()-1
					self.tabWidget.setCurrentIndex(self.ind)
				self.fileNames[self.ind] = fileName
				self.openFileMain()
	
	def openFileMain(self):
		if QFile.exists(self.fileNames[self.ind]):
			openfile = QFile(self.fileNames[self.ind])
			openfile.open(QIODevice.ReadOnly)
			html = QTextStream(openfile).readAll()
			openfile.close()
			self.editBoxes[self.ind].setPlainText(html)
			suffix = QFileInfo(self.fileNames[self.ind]).suffix()
			pt = not (suffix in ('re', 'md', 'markdown', 'mdown', 'mkd', 'mkdn', 'rst', 'rest', 'html', 'htm'))
			self.actionPlainText.setChecked(pt)
			self.enablePlainText(pt)
			self.setCurrentFile()
			self.setWindowModified(False)
	
	def saveFile(self):
		self.saveFileMain(dlg=False)
	
	def saveFileAs(self):
		self.saveFileMain(dlg=True)
	
	def saveAll(self):
		oldind = self.ind
		for self.ind in range(self.tabWidget.count()):
			if self.fileNames[self.ind] and QFileInfo(self.fileNames[self.ind]).isWritable():
				self.saveFileWrapper(self.fileNames[self.ind])
				self.editBoxes[self.ind].document().setModified(False)
		self.ind = oldind
	
	def saveFileMain(self, dlg):
		if (not self.fileNames[self.ind]) or dlg:
			if self.actionPlainText.isChecked():
				defaultExt = self.tr("Plain text (*.txt)")
				ext = ".txt"
			elif self.getParser() == PARSER_DOCUTILS:
				defaultExt = self.tr("ReStructuredText files")+" (*.rest *.rst *.txt)"
				ext = ".rst"
			elif self.getParser() == PARSER_HTML:
				defaultExt = self.tr("HTML files")+" (*.html *.htm)"
				ext = ".html"
			else:
				defaultExt = self.tr("Markdown files")+" (*.re *.md *.markdown *.mdown *.mkd *.mkdn *.txt)"
				ext = ".mkd"
				if QSettings().contains('defaultExt'):
					ext = QSettings().value('defaultExt').toString()
			self.fileNames[self.ind] = QFileDialog.getSaveFileName(self, self.tr("Save file"), "", defaultExt)
			if self.fileNames[self.ind] and QFileInfo(self.fileNames[self.ind]).suffix().isEmpty():
				self.fileNames[self.ind].append(ext)
		if self.fileNames[self.ind]:
			self.setCurrentFile()
		if QFileInfo(self.fileNames[self.ind]).isWritable() or not QFile.exists(self.fileNames[self.ind]):
			if self.fileNames[self.ind]:
				self.saveFileWrapper(self.fileNames[self.ind])
				self.editBoxes[self.ind].document().setModified(False)
				self.setWindowModified(False)
		else:
			self.setWindowModified(self.isWindowModified())
			QMessageBox.warning(self, app_name, self.tr("Cannot save to file since it is read-only!"))
	
	def saveFileWrapper(self, fn):
		savefile = QFile(fn)
		savefile.open(QIODevice.WriteOnly)
		savestream = QTextStream(savefile)
		savestream << self.editBoxes[self.ind].toPlainText()
		savefile.close()
	
	def saveHtml(self, fileName):
		if QFileInfo(fileName).suffix().isEmpty():
			fileName.append(".html")
		htmlFile = QFile(fileName)
		htmlFile.open(QIODevice.WriteOnly)
		html = QTextStream(htmlFile)
		text = self.parseText()
		if self.getParser() == PARSER_HTML:
			html << text << "\n"
			htmlFile.close()
			return
		html << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN\">\n"
		html << "<html>\n<head>\n"
		html << "  <meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\">\n"
		html << QString("  <meta name=\"generator\" content=\"%1 %2\">\n").arg(app_name, app_version)
		html << "  <title>" + self.getDocumentTitle() + "</title>\n"
		html << "</head>\n<body>\n"
		html << text
		html << "\n</body>\n</html>\n"
		htmlFile.close()
	
	def textDocument(self):
		if not self.actionPlainText.isChecked():
			text = self.parseText()
		td = QTextDocument()
		td.setMetaInformation(QTextDocument.DocumentTitle, self.getDocumentTitle())
		if self.ss:
			td.setDefaultStyleSheet(self.ss)
		if self.actionPlainText.isChecked():
			td.setPlainText(self.editBoxes[self.ind].toPlainText())
		else:
			td.setHtml('<html><body>'+text+'</body></html>')
		if self.font:
			td.setDefaultFont(self.font)
		return td
	
	def saveOdf(self):
		fileName = QFileDialog.getSaveFileName(self, self.tr("Export document to ODT"), "", self.tr("OpenDocument text files (*.odt)"))
		if QFileInfo(fileName).suffix().isEmpty():
			fileName.append(".odt")
		writer = QTextDocumentWriter(fileName)
		writer.setFormat("odf")
		writer.write(self.textDocument())
	
	def saveFilePerfect(self):
		fileName = None
		fileName = QFileDialog.getSaveFileName(self, self.tr("Save file"), "", self.tr("HTML files (*.html *.htm)"))
		if fileName:
			self.saveHtml(fileName)
	
	def standardPrinter(self):
		printer = QPrinter(QPrinter.HighResolution)
		printer.setDocName(self.getDocumentTitle())
		printer.setCreator(app_name+" "+app_version)
		return printer
	
	def savePdf(self):
		fileName = QFileDialog.getSaveFileName(self, self.tr("Export document to PDF"), "", self.tr("PDF files (*.pdf)"))
		if fileName:
			if QFileInfo(fileName).suffix().isEmpty():
				fileName.append(".pdf")
			document = self.textDocument()
			printer = self.standardPrinter()
			printer.setOutputFormat(QPrinter.PdfFormat)
			printer.setOutputFileName(fileName)
			document.print_(printer)
	
	def printFile(self):
		document = self.textDocument()
		printer = self.standardPrinter()
		dlg = QPrintDialog(printer, self)
		dlg.setWindowTitle(self.tr("Print document"))
		if (dlg.exec_() == QDialog.Accepted):
			document.print_(printer)
	
	def printPreview(self):
		document = self.textDocument()
		printer = self.standardPrinter()
		preview = QPrintPreviewDialog(printer, self)
		self.connect(preview, SIGNAL("paintRequested(QPrinter*)"), document.print_)
		preview.exec_()
	
	def otherExport(self):
		if (self.actionPlainText.isChecked()):
			return QMessageBox.warning(self, app_name, self.tr('This function is not available in Plain text mode!'))
		s = QSettings()
		s.beginGroup('Export')
		types = []
		for i in s.allKeys():
			types.append(i)
		item, ok = QInputDialog.getItem(self, app_name, self.tr('Select type'), types, 0, False)
		if ok:
			fileName = QFileDialog.getSaveFileName(self, self.tr('Export document'))
			if QFileInfo(fileName).suffix().isEmpty():
				fileName.append('.'+item)
			args = str(s.value(item).toString()).split()
			self.saveFileWrapper('temp.re')
			for i in range(len(args)):
				if args[i] == '%of':
					args[i] = 'out.'+str(item)
				elif args[i] == '%if':
					args[i] = 'temp.re'
			subprocess.Popen(args).wait()
			QFile('temp.re').remove()
			QFile('out.'+item).rename(fileName)
	
	def getDocumentTitle(self, baseName=False):
		"""Ensure that parseText() is called before this function!
		If 'baseName' is set to True, file basename will be used."""
		realTitle = ''
		text = unicode(self.editBoxes[self.ind].toPlainText())
		if not self.actionPlainText.isChecked():
			parser = self.getParser()
			if parser == PARSER_DOCUTILS:
				realTitle = publish_parts(text, writer_name='html')['title']
			elif parser == PARSER_MARKDOWN:
				try:
					realTitle = str.join(' ', md.Meta['title'])
				except:
					# Meta extension not installed
					pass
		if realTitle and not baseName:
			return realTitle
		elif self.fileNames[self.ind]:
			return QFileInfo(self.fileNames[self.ind]).completeBaseName()
		else:
			return self.tr("New document")
	
	def saveGDocs(self):
		settings = QSettings()
		login = settings.value("GDocsLogin").toString()
		passwd = settings.value("GDocsPasswd").toString()
		loginDialog = LogPassDialog(login, passwd)
		if loginDialog.exec_() == QDialog.Accepted:
			login = loginDialog.loginEdit.text()
			passwd = loginDialog.passEdit.text()
			if self.actionPlainText.isChecked():
				self.saveFileWrapper('temp.txt')
			else:
				self.saveHtml('temp.html')
			gdClient = gdata.docs.service.DocsService(source=app_name)
			try:
				gdClient.ClientLogin(unicode(login), unicode(passwd))
			except gdata.service.BadAuthentication:
				QMessageBox.warning(self, app_name, self.tr("Incorrect user name or password!"))
			else:
				settings.setValue("GDocsLogin", login)
				settings.setValue("GDocsPasswd", passwd)
				if self.actionPlainText.isChecked():
					ms = MediaSource(file_path='temp.txt', content_type='text/plain')
				else:
					ms = MediaSource(file_path='temp.html', content_type='text/html')
				entry = gdClient.Upload(ms, unicode(self.getDocumentTitle()))
				link = entry.GetAlternateLink().href
				if self.actionPlainText.isChecked():
					QFile('temp.txt').remove()
				else:
					QFile('temp.html').remove()
				QDesktopServices.openUrl(QUrl(link))
	
	def autoSaveActive(self):
		return self.autoSave and self.fileNames[self.ind] and \
		QFileInfo(self.fileNames[self.ind]).isWritable()
	
	def modificationChanged(self, changed):
		if self.autoSaveActive():
			changed = False
		self.actionSave.setEnabled(changed)
		self.setWindowModified(changed)
	
	def clipboardDataChanged(self):
		self.actionPaste.setEnabled(qApp.clipboard().mimeData().hasText())
	
	def insertTag(self, num):
		if num:
			ut = self.usefulTags[num-1]
			hc = not ut in ('td', 'tr')
			arg = ''
			if ut == 'span':
				arg = ' style=""'
			tc = self.editBoxes[self.ind].textCursor()
			if hc:
				toinsert = '<'+ut+arg+'>'+tc.selectedText()+'</'+ut+'>'
				tc.removeSelectedText
				tc.insertText(toinsert)
			else:
				tc.insertText('<'+ut+arg+'>'+tc.selectedText())
		self.tagsBox.setCurrentIndex(0)
	
	def insertSymbol(self, num):
		if num:
			self.editBoxes[self.ind].insertPlainText('&'+self.usefulChars[num-1]+';')
		self.symbolBox.setCurrentIndex(0)
	
	def maybeSave(self, ind):
		if self.autoSaveActive():
			self.saveFileWrapper(self.fileNames[self.ind])
			return True
		if not self.editBoxes[ind].document().isModified():
			return True
		self.tabWidget.setCurrentIndex(ind)
		ret = QMessageBox.warning(self, app_name, self.tr("The document has been modified.\nDo you want to save your changes?"), \
		QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
		if ret == QMessageBox.Save:
			self.saveFileMain(False)
			return True
		elif ret == QMessageBox.Cancel:
			return False
		return True
	
	def closeEvent(self, closeevent):
		accept = True
		for self.ind in range(self.tabWidget.count()):
			if not self.maybeSave(self.ind):
				accept = False
		if accept:
			closeevent.accept()
		else:
			closeevent.ignore()
	
	def viewHtml(self):
		HtmlDlg = HtmlDialog(self)
		HtmlDlg.textEdit.setPlainText(self.parseText())
		winTitle = self.tr('New document')
		if self.fileNames[self.ind]:
			winTitle = QFileInfo(self.fileNames[self.ind]).fileName()
		HtmlDlg.setWindowTitle(winTitle+" ("+self.tr("HTML code")+") "+QChar(0x2014)+" "+app_name)
		HtmlDlg.show()
		HtmlDlg.raise_()
		HtmlDlg.activateWindow()
	
	def aboutDialog(self):
		QMessageBox.about(self, self.tr('About %1').arg(app_name), \
		'<p><b>'+app_name+' '+app_version+'</b><br>'+self.tr('Simple but powerful editor for Markdown and ReStructuredText') \
		+'</p><p>'+self.tr('Author: Dmitry Shachnev, 2011') \
		+'<br><a href="http://sourceforge.net/p/retext/">'+self.tr('Website') \
		+'</a> | <a href="http://daringfireball.net/projects/markdown/syntax">'+self.tr('Markdown syntax') \
		+'</a> | <a href="http://docutils.sourceforge.net/docs/user/rst/quickref.html">' \
		+self.tr('ReST syntax')+'</a></p>')
	
	def enablePlainText(self, value):
		self.aptc[self.ind] = value
		self.enablePlainTextMain(value)
		self.updatePreviewBox()
	
	def enablePlainTextMain(self, value):
		self.actionPerfectHtml.setDisabled(value)
		self.actionViewHtml.setDisabled(value)
		self.tagsBox.setDisabled(value)
		self.symbolBox.setDisabled(value)
	
	def setDocUtilsDefault(self, yes):
		self.useDocUtils = yes
		QSettings().setValue('useReST', yes)
		self.updatePreviewBox()
	
	def getParser(self):
		if self.fileNames[self.ind]:
			suffix = QFileInfo(self.fileNames[self.ind]).suffix()
			if suffix in ('md', 'markdown', 'mdown', 'mkd', 'mkdn'):
				if use_md:
					return PARSER_MARKDOWN
				else:
					return PARSER_NA
			elif suffix in ('rest', 'rst'):
				if use_docutils:
					return PARSER_DOCUTILS
				else:
					return PARSER_NA
			elif suffix in ('html', 'htm'):
				return PARSER_HTML
		if not (use_docutils or use_md):
			return PARSER_HTML
		elif use_docutils and (self.useDocUtils or not use_md):
			return PARSER_DOCUTILS
		else:
			return PARSER_MARKDOWN
	
	def parseText(self):
		htmltext = self.editBoxes[self.ind].toPlainText()
		parser = self.getParser()
		if parser == PARSER_HTML:
			return htmltext
		elif parser == PARSER_DOCUTILS:
			return publish_parts(unicode(htmltext), writer_name='html')['body']
		elif parser == PARSER_MARKDOWN:
			md.reset()
			return md.convert(unicode(htmltext))
		else:
			return '<p style="color: red">'\
			+self.tr('Could not parse file contents, check if you have the necessary module installed!')+'</p>'

def main(fileName):
	app = QApplication(sys.argv)
	app.setOrganizationName("ReText project")
	app.setApplicationName("ReText")
	RtTranslator = QTranslator()
	if not RtTranslator.load("retext_"+QLocale.system().name()):
		if not RtTranslator.load("retext_"+QLocale.system().name(), "/usr/lib/retext"):
			RtTranslator.load("retext_"+QLocale.system().name(), "/usr/share/retext/locale")
	QtTranslator = QTranslator()
	QtTranslator.load("qt_"+QLocale.system().name(), QLibraryInfo.location(QLibraryInfo.TranslationsPath))
	app.installTranslator(RtTranslator)
	app.installTranslator(QtTranslator)
	window = ReTextWindow()
	if QFile.exists(QString.fromUtf8(fileName)):
		window.openFileWrapper(QString.fromUtf8(fileName))
	window.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	if len(sys.argv) > 1:
		main(sys.argv[1])
	else:
		main("")
