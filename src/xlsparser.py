#!/usr/bin/env python2
########################################################################
#
#  Copyright (c) 2011 Sergey Kishchenko
#  
#  Permission is hereby granted, free of charge, to any person
#  obtaining a copy of this software and associated documentation
#  files (the "Software"), to deal in the Software without
#  restriction, including without limitation the rights to use,
#  copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following
#  conditions:
#  
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#  
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#  OTHER DEALINGS IN THE SOFTWARE.
#
########################################################################
import xlsrecord


############## Common parsers ##########################################
class ParseException(Exception):
    pass

class TokenStream(object):
    def __init__(self, tokens):
        self.tokens = tokens
        self.currentIndex = 0
        self.maxCurrentIndex = 0
    
    def readToken(self):
        if self.eof():
            return None
        token = self.tokens[self.currentIndex]
        self.currentIndex += 1
        self.maxCurrentIndex = max(self.currentIndex, self.maxCurrentIndex)
        return token
    
    def eof(self):
        if self.currentIndex >= len(self.tokens):
            return True
        else:
            return False
        


class BaseParser(object):
    def parse(self, stream):
        parser = getattr(self, 'PARSER', None)
        if parser is None:
            return None
        else:
            return parser.parse(stream)

    def __str__(self):
        parser = getattr(self, 'PARSER', None)
        if parser is None:
            return "NONIMPL(%s)" % self.__class__
        else:
            return str(parser)
        
    def __lshift__(self, other):
        if isinstance(self, Seq):
            self.appendParser(other)
            return self
        else:
            return Seq(self, other)
        
def safeParse(parser, stream):
    #print "TRACE:[%s,%s]" % (str(parser), str(stream.tokens[stream.currentIndex]))  

    parsed = None
    try:
        curIndex = stream.currentIndex
        parsed = parser.parse(stream)
    except ParseException as exc:
        stream.currentIndex = curIndex
        raise
    return parsed

def getParsedOrNone(parser, stream):
    parsed = None
    try:
        parsed = safeParse(parser, stream)
    except ParseException:
        pass
    return parsed

class Term(BaseParser):
    def __init__(self, tokenType):
        self.__tokenType = tokenType
        
    def parse(self, stream):
        curIndex = stream.currentIndex
        token = stream.readToken()
        if not token is None and isinstance(token, self.__tokenType):
            return token
        else:
            stream.currentIndex = curIndex
            return None
        
    def __str__(self):
        return 'Term(%s)' % str(self.__tokenType)

class Opt(BaseParser):
    def __init__(self, parser):
        self.__parser = parser

    def parse(self, stream):
        return getParsedOrNone(self.__parser, stream)
    
    def __str__(self):
        return 'Opt(%s)' % str(self.__parser)

class Req(BaseParser):
    def __init__(self, parser):
        self.__parser = parser
    
    def parse(self, stream):
        parsed = safeParse(self.__parser, stream)
        if parsed is None:
            currentToken = "<<<End Of Token Stream>>>"
            if stream.currentIndex < len(stream.tokens):
                currentToken = stream.tokens[stream.currentIndex]
            raise ParseException("%s failed but it is required, next token is [%s]" % 
                                 (str(self.__parser), str(currentToken)))
        return parsed
    
    def __str__(self):
        return 'Req(%s)' % str(self.__parser)
            
class AnyButThis(BaseParser):
    def __init__(self, parser):
        self.__parser = parser
    
    def parse(self, stream):
        curIndex = stream.currentIndex
        parsed = getParsedOrNone(self.__parser, stream)
        if parsed is None:
            return ('any', stream.readToken())
        else:
            stream.currentIndex = curIndex
            return None

    def __str__(self):
        return 'AnyButThis(%s)' % str(self.__parser)

class Many(BaseParser):
    def __init__(self, group, parser, min=0, max=-1):
        self.__group = group
        self.__parser = parser
        self.__min = min
        self.__max = max
        
    def parse(self, stream):
        if self.__min == 0 and self.__max == 0:
            return None
        x = 0
        parsedList = []
        while True:
            parsed = getParsedOrNone(self.__parser, stream)
            if parsed is None:
                break
            parsedList.append(parsed)
            x += 1
            if self.__max != -1 and x>=self.__max:
                break
        if x<self.__min:
            raise ParseException("%s should occur at least %s times" % (self.__parser,self.__min))
        return (self.__group, parsedList)

    def __str__(self):
        return 'Many(%s,%s,min=%s,max=%s)' % (self.__group, str(self.__parser), self.__min, self.__max)

class OneOf(BaseParser):
    def __init__(self, *args):
        self.__parsers = args
        
    def parse(self, stream):
        for parser in self.__parsers:
            parsed = getParsedOrNone(parser, stream)
            if not parsed is None:
                return parsed
        raise ParseException("No suitable options: [%s]" % ','.join(str(x) for x in self.__parsers))
    
    def __str__(self):
        return 'OneOf(%s)' % ','.join(str(x) for x in self.__parsers)

class Seq(BaseParser):
    def __init__(self, *args):
        self.__parsers = list(args)
        
    def parse(self, stream):
        parsedList = []
        for parser in self.__parsers:
            parsed = safeParse(parser, stream)
            if not parsed is None:
                parsedList.append(parsed)
        return parsedList
    
    def appendParser(self, parser):
        self.__parsers.append(parser)
        
    def __str__(self):
        return 'Seq(%s)' % ','.join(str(x) for x in self.__parsers)

class Group(BaseParser):
    def __init__(self, name, parser):
        self.__name = name
        self.__parser = parser
    
    def parse(self, stream):
        parsed = self.__parser.parse(stream)
        if not parsed is None:
            return (self.__name, parsed)
        else:
            return None
    
    def __str__(self):
        return 'Group(%s, %s)' % (self.__name, str(self.__parser))


############## Specific parsers ##########################################
class WriteProtect(BaseParser): pass
class SheetExt(BaseParser): pass
class WebPub(BaseParser): pass
class HFPicture(BaseParser): pass

class Header(BaseParser):
    PARSER = Term(xlsrecord.Header)

class Footer(BaseParser):
    PARSER = Term(xlsrecord.Footer)

class HCenter(BaseParser):
    PARSER = Term(xlsrecord.HCenter)

class VCenter(BaseParser):
    PARSER = Term(xlsrecord.VCenter)

class MarginBaseParser(BaseParser): pass
class LeftMargin(MarginBaseParser): pass        
class RightMargin(MarginBaseParser): pass        
class TopMargin(MarginBaseParser): pass        
class BottomMargin(MarginBaseParser): pass        
class Pls(BaseParser): 
    PARSER = Term(xlsrecord.Pls)

class Continue(BaseParser):
    PARSER = Term(xlsrecord.Continue)


class Setup(BaseParser):
    PARSER = Term(xlsrecord.Setup)

class PAGESETUP(BaseParser):
    #PAGESETUP = Header Footer HCenter VCenter [LeftMargin] [RightMargin] [TopMargin]
    #[BottomMargin] [Pls *Continue] Setup
    PARSER = Group('page-setup', Req(Header()) << Req(Footer()) << Req(HCenter()) << Req(VCenter()) <<
                   LeftMargin() << RightMargin() << TopMargin() << BottomMargin() << 
                   Seq(Pls(), Many('continues', Continue())) << Setup())


class PrintSize(BaseParser):
    PARSER = Term(xlsrecord.PrintSize)

class HeaderFooter(BaseParser): pass        
class BACKGROUND(BaseParser): pass        

class Fbi(BaseParser):
    PARSER = Term(xlsrecord.Fbi)
    
class Fbi2(BaseParser): pass        
class ClrtClient(BaseParser): pass        

class PROTECTION(BaseParser):
    PARSER = Term(xlsrecord.Protect)

class Palette(BaseParser): pass        
class SXViewLink(BaseParser): pass        
class PivotChartBits(BaseParser): pass        
class SBaseRef(BaseParser): pass        
class MsoDrawingGroup(BaseParser): pass        


class MSODRAWING(BaseParser):
    PARSER = Term(xlsrecord.MSODrawing)

class TxO(BaseParser):
    PARSER = Term(xlsrecord.TxO)


class TEXTOBJECT(BaseParser): 
    # TEXTOBJECT = TxO *Continue
    PARSER = Group('text-object-group', Req(TxO()) << Many('conitnues', Continue()))

class Obj(BaseParser):
    PARSER = Term(xlsrecord.Obj)

class CHART(BaseParser): 
    def parse(self, stream):
        return Group('chart', Req(BOF()) << Req(CHARTSHEETCONTENT())).parse(stream)


class OBJ(BaseParser):
    # OBJ = Obj *Continue *CHART
    PARSER = Group('obj-group', Req(Obj()) << Many('conitnues', Continue()) << Many('charts', CHART()))

class MsoDrawingSelection(BaseParser):
    PARSER = Term(xlsrecord.MSODrawingSelection)
    

class OBJECTS(BaseParser):
    #*(MSODRAWING *(TEXTOBJECT / OBJ)) [MsoDrawingSelection]
    PARSER = Group('objects', Many('drawings', Seq(Req(MSODRAWING()), 
                                                   Many('obj-list', 
                                                        OneOf(TEXTOBJECT(), OBJ())))) << 
                              MsoDrawingSelection()) 

class Units(BaseParser):
    PARSER = Term(xlsrecord.Units)

class Chart(BaseParser):
    PARSER = Term(xlsrecord.Chart)

class Begin(BaseParser):
    PARSER = Term(xlsrecord.Begin)

class End(BaseParser):
    PARSER = Term(xlsrecord.End)

class PlotArea(BaseParser):
    PARSER = Term(xlsrecord.PlotArea)

class CrtLink(BaseParser):
    PARSER = Term(xlsrecord.CrtLink)

class FONTLIST(BaseParser): pass        

class Frame(BaseParser):
    PARSER = Term(xlsrecord.Frame)

class LineFormat(BaseParser):
    PARSER = Term(xlsrecord.LineFormat)

class AreaFormat(BaseParser):
    PARSER = Term(xlsrecord.AreaFormat)
    
class PICF(BaseParser): pass # PICF = Begin PicF End

class GelFrame(BaseParser):
    PARSER = Term(xlsrecord.GelFrame)

class GELFRAME(BaseParser): 
    #GELFRAME = 1*2GelFrame *Continue [PICF]
    PARSER = Group('gel-frame-root', Many('gel-frame-list', GelFrame(), min=1, max=2) << 
                                     Many('continue-list', Continue()) << Opt(PICF()))

class SHAPEPROPS(BaseParser): pass        

class FRAME(BaseParser):
    PARSER = Group('frame', Req(Frame()) << Req(Begin()) << Req(LineFormat()) << Req(AreaFormat()) <<
                   Opt(GELFRAME()) << Opt(SHAPEPROPS()) << Req(End()))


class Scl(BaseParser):
    PARSER = Term(xlsrecord.Scl)

class PlotGrowth(BaseParser):
    PARSER = Term(xlsrecord.PlotGrowth)

class Series(BaseParser):
    PARSER = Term(xlsrecord.Series)

class SeriesText(BaseParser):
    PARSER = Term(xlsrecord.SeriesText)

class BRAI(BaseParser):
    PARSER = Term(xlsrecord.Brai)

class AI(BaseParser):
    PARSER = Req(BRAI()) << SeriesText()

class SerParent(BaseParser): pass        
class SerAuxTrend(BaseParser): pass        
class SerAuxErrBar(BaseParser): pass        
class SerToCrt(BaseParser): 
    PARSER = Term(xlsrecord.SerToCrt)
    
class LegendException(BaseParser): pass        

class DataFormat(BaseParser):
    PARSER = Term(xlsrecord.DataFormat)

class Chart3DBarShape(BaseParser):
    PARSER = Term(xlsrecord.Chart3DBarShape)

class PieFormat(BaseParser): 
    PARSER = Term(xlsrecord.PieFormat)

class SerFmt(BaseParser):  
    PARSER = Term(xlsrecord.SerFmt)

class MarkerFormat(BaseParser): 
    PARSER = Term(xlsrecord.MarkerFormat)

class Text(BaseParser):
    PARSER = Term(xlsrecord.Text)

class Pos(BaseParser):
    PARSER = Term(xlsrecord.Pos)

class FontX(BaseParser):
    PARSER = Term(xlsrecord.FontX)

class AlRuns(BaseParser): pass

class ObjectLink(BaseParser): 
    PARSER = Term(xlsrecord.ObjectLink)
    
class DataLabExtContents(BaseParser): 
    PARSER = Term(xlsrecord.DataLabExtContents)

class CrtLayout12(BaseParser): pass
class CRTMLFRT(BaseParser): pass
class TEXTPROPS(BaseParser): pass


class AttachedLabel(BaseParser):
    PARSER = Term(xlsrecord.AttachedLabel)

class ATTACHEDLABEL(BaseParser):
    #ATTACHEDLABEL = Text Begin Pos [FontX] [AlRuns] AI [FRAME] [ObjectLink] [DataLabExtContents]
    #[CrtLayout12] [TEXTPROPS] [CRTMLFRT] End
    PARSER = Group('attached-label-struct', Req(Text()) << Req(Begin()) << Req(Pos()) << FontX() << AlRuns() << Req(AI()) <<
                Opt(FRAME()) << ObjectLink() << DataLabExtContents() << CrtLayout12() << TEXTPROPS() << CRTMLFRT() << Req(End()))

class SS(BaseParser):
    #SS = DataFormat Begin [Chart3DBarShape] [LineFormat AreaFormat PieFormat] [SerFmt]
    #[GELFRAME] [MarkerFormat] [AttachedLabel] *2SHAPEPROPS [CRTMLFRT] End
    PARSER = Group('ss', Seq(Req(DataFormat()), Req(Begin()), Chart3DBarShape(), 
                             Opt(Seq(Req(LineFormat()), Req(AreaFormat()), Req(PieFormat()))),
                             SerFmt(), Opt(GELFRAME()), MarkerFormat(), AttachedLabel(), 
                             Many('shape-props-list', SHAPEPROPS(), max=2), CRTMLFRT(),
                             Req(End())))

class StartBlock(BaseParser):
    PARSER = Term(xlsrecord.StartBlock)

class EndBlock(BaseParser):
    PARSER = Term(xlsrecord.EndBlock)

class SERIESFORMAT(BaseParser):
    #SERIESFORMAT = Series Begin 4AI *SS (SerToCrt / (SerParent (SerAuxTrend / SerAuxErrBar)))
    #*(LegendException [Begin ATTACHEDLABEL [TEXTPROPS] End]) End
    PARSER = Group('series-fmt', Req(Series()) << Req(Begin()) << Many('ai-list', AI(), min=4, max=4) <<
                Many('ss-list', SS()) << OneOf(SerToCrt(), Seq(SerParent(), OneOf(SerAuxTrend(), SerAuxErrBar()))) <<
                Many('legend-exceptions', Group('legend-exception-root', 
                                                Seq(Req(LegendException()), 
                                                    Seq(Req(Begin()), Req(ATTACHEDLABEL()), TEXTPROPS(), Req(End()))))) <<
                EndBlock() << Req(End()))


        
class ShtProps(BaseParser):
    PARSER = Term(xlsrecord.CHProperties)

class DataLabExt(BaseParser): pass
class StartObject(BaseParser): pass
class EndObject(BaseParser): pass

class DefaultText(BaseParser):
    PARSER = Term(xlsrecord.DefaultText)

class DFTTEXT(BaseParser):
    #DFTTEXT = [DataLabExt StartObject] DefaultText ATTACHEDLABEL [EndObject]
    PARSER = Group('dft-text', Seq(Opt(Seq(Req(DataLabExt()), Req(StartObject()))),
                                   Req(DefaultText()), Req(ATTACHEDLABEL()),
                                   EndObject()))

class AxesUsed(BaseParser):
    PARSER = Term(xlsrecord.AxesUsed)

class AxisParent(BaseParser):
    PARSER = Term(xlsrecord.AxisParent)

class Axis(BaseParser):
    PARSER = Term(xlsrecord.CHAxis)

class CatSerRange(BaseParser):
    PARSER = Term(xlsrecord.CHLabelRange)

class AxcExt(BaseParser):
    PARSER = Term(xlsrecord.AxcExt)

class CatLab(BaseParser): 
    PARSER = Term(xlsrecord.CatLab)

class IFmtRecord(BaseParser): pass

class Tick(BaseParser):
    PARSER = Term(xlsrecord.Tick)

class AxisLine(BaseParser):
    PARSER = Term(xlsrecord.AxisLine)


class TextPropsStream(BaseParser): pass
class ContinueFrt12(BaseParser): pass

class ChartFrtInfo(BaseParser):
    PARSER = Term(xlsrecord.ChartFrtInfo)


class AXS(BaseParser):
    # AXS = [IFmtRecord] [Tick] [FontX] *4(AxisLine LineFormat) [AreaFormat] [GELFRAME]
    # *4SHAPEPROPS [TextPropsStream *ContinueFrt12]
    PARSER = Group('axs', IFmtRecord() << Tick() << FontX() << 
                Many('axis-lines', Seq(Req(AxisLine()), Req(LineFormat())), max=4) <<
                AreaFormat() << Opt(GELFRAME()) << Many('shape-props-list', SHAPEPROPS(), max=4) << 
                Opt(Seq(Req(TextPropsStream()), Many('continue-frt12-list', ContinueFrt12()))))

class IVAXIS(BaseParser):
    # original ABNF:
    # IVAXIS = Axis Begin [CatSerRange] AxcExt [CatLab] AXS [CRTMLFRT] End
    # it seems it's usual too have several future records indicators just after AxcExt and before the End:
    # IVAXIS = Axis Begin [CatSerRange] AxcExt ([ChartFrtInfo] *StartBlock) [CatLab] AXS [CRTMLFRT] [EndBlock] End
    
    PARSER = Group('ivaxis', Req(Axis()) << Req(Begin()) << CatSerRange() << Req(AxcExt()) << 
                Group('future', Seq(ChartFrtInfo(), 
                                    Many('start-blocks', StartBlock()))) << CatLab() << 
                Req(AXS()) << Opt(CRTMLFRT()) << EndBlock() << Req(End()))

class ValueRange(BaseParser):
    PARSER = Term(xlsrecord.CHValueRange)

class AXM(BaseParser): pass

class DVAXIS(BaseParser):
    #DVAXIS = Axis Begin [ValueRange] [AXM] AXS [CRTMLFRT] End
    PARSER = Group('dvaxis', Req(Axis()) << Req(Begin()) << ValueRange() << AXM() << Req(AXS()) << CRTMLFRT() << 
                Req(End()))

class SERIESAXIS(BaseParser): 
    #SERIESAXIS = Axis Begin [CatSerRange] AXS [CRTMLFRT] End
    PARSER = Group('series-axis', Req(Axis()) << Req(Begin()) << CatSerRange() << 
                                  Req(AXS()) << Opt(CRTMLFRT()) << Req(End()))

class AXES(BaseParser):
    #AXES = [IVAXIS DVAXIS [SERIESAXIS] / DVAXIS DVAXIS] *3ATTACHEDLABEL [PlotArea FRAME]
    # TODO: recheck it. The rule above leaks some brackets :(
    PARSER = Group('axes', Seq(OneOf(Seq(Req(IVAXIS()), Req(DVAXIS()), Opt(SERIESAXIS())), 
                                     Seq(Req(DVAXIS()), Req(DVAXIS()))), 
                               Many('attached-labels', ATTACHEDLABEL(), max=3),
                               Opt(Seq(Req(PlotArea()), Req(FRAME())))))


class ChartFormat(BaseParser):
    PARSER = Term(xlsrecord.ChartFormat)

class BobPop(BaseParser): 
    PARSER = Term(xlsrecord.BobPop)

class BobPopCustom(BaseParser): pass

class Bar(BaseParser):
    PARSER = Term(xlsrecord.CHBar)

class Line(BaseParser): 
    PARSER = Term(xlsrecord.CHLine)
    
class Pie(BaseParser):
    PARSER = Term(xlsrecord.CHPie)
    
class Area(BaseParser):
    PARSER = Term(xlsrecord.CHArea)
    
class Scatter(BaseParser): 
    PARSER = Term(xlsrecord.CHScatter)
    
class Radar(BaseParser): 
    PARSER = Term(xlsrecord.CHRadar)
    
class RadarArea(BaseParser): pass

class Surf(BaseParser): 
     PARSER = Term(xlsrecord.CHSurf)

class SeriesList(BaseParser):  
     PARSER = Term(xlsrecord.SeriesList)
     
class Chart3d(BaseParser): 
    PARSER = Term(xlsrecord.Chart3d)


class Legend(BaseParser):
    PARSER = Term(xlsrecord.Legend)

class LD(BaseParser):
    #LD = Legend Begin Pos ATTACHEDLABEL [FRAME] [CrtLayout12] [TEXTPROPS] [CRTMLFRT] End
    PARSER = Group('ld', Req(Legend()) << Req(Begin()) << Req(Pos()) << Req(ATTACHEDLABEL()) << 
                Opt(FRAME()) << CrtLayout12() << TEXTPROPS() << CRTMLFRT() << Req(End()))

class DropBar(BaseParser):
    PARSER = Term(xlsrecord.DropBar)

class DROPBAR(BaseParser): 
    # DROPBAR = DropBar Begin LineFormat AreaFormat [GELFRAME] [SHAPEPROPS] End
    PARSER = Group('drop-bar-root', Req(DropBar()) << Req(Begin()) << Req(LineFormat()) << 
                                    Req(AreaFormat()) << Opt(GELFRAME()) << Opt(SHAPEPROPS()) << 
                                    Req(End()))
class CrtLine(BaseParser): 
    PARSER = Term(xlsrecord.CrtLine)
    
class CrtLayout12A(BaseParser): pass

class Dat(BaseParser): 
    PARSER = Term(xlsrecord.Dat)

class DAT(BaseParser): 
    #DAT = Dat Begin LD End
    PARSER = Group('dat-root', Req(Dat()) << Req(Begin()) << Req(LD()) << Req(End()))


class CRT(BaseParser):
    # It seems 2DROPBAR should be considered *2DROPBAR
    #CRT = ChartFormat Begin (Bar / Line / (BopPop [BopPopCustom]) / Pie / Area / Scatter / Radar /
    #RadarArea / Surf) CrtLink [SeriesList] [Chart3d] [LD] [*2DROPBAR] *4(CrtLine LineFormat)
    #*2DFTTEXT [DataLabExtContents] [SS] *4SHAPEPROPS End
    # It seems there are optional StartBlock and EndBlock on the last line:
    #*2DFTTEXT [StartBlock] [DataLabExtContents]  [SS] *4SHAPEPROPS [EndBlock] End
    
    
    PARSER = Group('crt', Req(ChartFormat()) << Req(Begin()) << OneOf(Bar(), Line(), Opt(Seq(Req(BobPop()), BobPopCustom())),
                                                                  Pie(), Area(), Scatter(), Radar(),
                                                                  RadarArea(), Surf()) <<
                Req(CrtLink()) << SeriesList() << Chart3d() << Opt(LD()) << Many('drop-bars', DROPBAR(), max=2) << 
                Many('crt-lines', Seq(Req(CrtLine()), 
                                      Req(LineFormat()))) << Many('dft-texts', DFTTEXT()) <<
                StartBlock() << DataLabExtContents() << Opt(SS()) << 
                Many('shape-props-list', SHAPEPROPS(), max=4) << EndBlock() << Req(End()))

class AXISPARENT(BaseParser):
    # Original:
    # AXISPARENT = AxisParent Begin Pos [AXES] 1*4CRT End
    # It seems AXISPARENT can have EndBlock before End:
    # AXISPARENT = AxisParent Begin Pos [AXES] 1*4CRT [EndBlock] End
    PARSER = Group('axis-root', Req(AxisParent()) << Req(Begin()) << Req(Pos()) <<
                                  Opt(AXES()) << Many('crt-list', CRT(), min=1, max=4) <<
                                  EndBlock() <<
                                  Req(End()))






class CHARTFORMATS(BaseParser):
    #CHARTFOMATS = Chart Begin *2FONTLIST Scl PlotGrowth [FRAME] *SERIESFORMAT *SS ShtProps
    #*2DFTTEXT AxesUsed 1*2AXISPARENT [CrtLayout12A] [DAT] *ATTACHEDLABEL [CRTMLFRT]
    #*([DataLabExt StartObject] ATTACHEDLABEL [EndObject]) [TEXTPROPS] *2CRTMLFRT End
    # It seems it is possible to have optional EndBlock just before an end
    PARSER = Group('chart-fmt', Req(Chart()) << Req(Begin()) << Many('font-lists', FONTLIST(), max=2) <<
                Req(Scl()) << Req(PlotGrowth()) << Opt(FRAME()) << Many('series-fmt-list', SERIESFORMAT()) <<
                Many('ss-list', SS()) << Req(ShtProps()) << Many('dft-texts', DFTTEXT(), max=2) <<
                Req(AxesUsed()) << Many('axis-roots', AXISPARENT(), min=1, max=2) <<
                CrtLayout12A() << Opt(DAT()) << Many('attached-labels', ATTACHEDLABEL()) <<
                Opt(CRTMLFRT()) << Many('datalab-exts', Seq(Opt(Seq(Req(DataLabExt()), 
                                                                    Req(StartObject()))), 
                                                            Req(ATTACHEDLABEL()), 
                                                            EndObject())) <<
                Opt(TEXTPROPS()) << Many('crtmlfrt-list', CRTMLFRT()) << EndBlock() << Req(End()))

class Dimensions(BaseParser):
    PARSER = Term(xlsrecord.Dimensions)

class SIIndex(BaseParser):
    PARSER = Term(xlsrecord.SIIndex)

class Number(BaseParser):
    PARSER = Term(xlsrecord.Number)


class BoolErr(BaseParser): pass
class Blank(BaseParser): pass

class Label(BaseParser):
    PARSER = Term(xlsrecord.Label)

class SERIESDATA(BaseParser):
    #SERIESDATA = Dimensions 3(SIIndex *(Number / BoolErr / Blank / Label))
    PARSER = Group('series-data', Req(Dimensions()) << Many('si-index-list', 
                                                          Seq(Req(SIIndex()), 
                                                              Many('values', 
                                                                   OneOf(Number(), BoolErr(), 
                                                                         Blank(), Label()))), 
                                                          min=3, max=3))

class CodeName(BaseParser):
    PARSER = Term(xlsrecord.CodeName)

class Window2(BaseParser):
    PARSER = Term(xlsrecord.Window2)

class PLV(BaseParser):
    PARSER = Term(xlsrecord.PLV)

class PLVMac(BaseParser):
    PARSER = Term(xlsrecord.PLVMac)

class Scl(BaseParser): pass
class Pane(BaseParser): pass
class Selection(BaseParser): 
    PARSER = Term(xlsrecord.Selection)


class WINDOW(BaseParser):
    # WINDOW = Window2 [PLV] [Scl] [Pane] *Selection
    PARSER = Group('window', Req(Window2()) << PLV() << Scl() << Pane() << Many('selections', Selection()))

class CUSTOMVIEW(BaseParser): pass

class EOF(BaseParser):
    PARSER = Term(xlsrecord.EOF)

class BOF(BaseParser):
    PARSER = Term(xlsrecord.BOF)

class CHARTSHEETCONTENT(BaseParser):
    #CHARTSHEETCONTENT = [WriteProtect] [SheetExt] [WebPub] *HFPicture PAGESETUP PrintSize
    #[HeaderFooter] [BACKGROUND] *Fbi *Fbi2 [ClrtClient] [PROTECTION] [Palette] [SXViewLink]
    #[PivotChartBits] [SBaseRef] [MsoDrawingGroup] OBJECTS Units CHARTFOMATS SERIESDATA
    #*WINDOW *CUSTOMVIEW [CodeName] [CRTMLFRT] EOF
    PARSER = Group('chartsheet-content', WriteProtect() << SheetExt() << WebPub() << Many('hf-pictures', HFPicture()) <<
              Req(PAGESETUP()) << Req(PrintSize()) << HeaderFooter() << BACKGROUND() <<
              Many('fbi-list', Fbi()) << Many('fbi2-list', Fbi2()) <<
              ClrtClient() << PROTECTION() << Palette() << SXViewLink() << PivotChartBits() << 
              SBaseRef() << MsoDrawingGroup() << Req(OBJECTS()) << Req(Units()) << 
              Req(CHARTFORMATS()) << Req(SERIESDATA()) << Many('windows', WINDOW()) <<
              Many('custom-views', CUSTOMVIEW()) << CodeName() << CRTMLFRT() << Req(EOF()))

class Uncalced(BaseParser): pass

class Index(BaseParser): 
    PARSER = Term(xlsrecord.Index)

class CalcMode(BaseParser): 
    PARSER = Term(xlsrecord.CalcMode)
    
class CalcCount(BaseParser):
    PARSER = Term(xlsrecord.CalcCount)
    
class CalcRefMode(BaseParser): 
    PARSER = Term(xlsrecord.CalcRefMode)
    
class CalcIter(BaseParser):
    PARSER = Term(xlsrecord.CalcIter)
    
class CalcDelta(BaseParser):
    PARSER = Term(xlsrecord.CalcDelta)
    
class CalcSaveRecalc(BaseParser): 
    PARSER = Term(xlsrecord.CalcSaveRecalc)
    
class PrintRowCol(BaseParser):
    PARSER = Term(xlsrecord.PrintRowCol)

class PrintGrid(BaseParser): 
    PARSER = Term(xlsrecord.PrintGrid)

class GridSet(BaseParser): 
    PARSER = Term(xlsrecord.GridSet)

class Guts(BaseParser): 
    PARSER = Term(xlsrecord.Guts)

class DefaultRowHeight(BaseParser):
    PARSER = Term(xlsrecord.DefRowHeight)

class WsBool(BaseParser): 
    PARSER = Term(xlsrecord.WsBool)

class Sync(BaseParser): pass
class LPr(BaseParser): pass
class HorizontalPageBreaks(BaseParser): pass
class VerticalPageBreaks(BaseParser): pass

class GLOBALS(BaseParser): 
    #GLOBALS = CalcMode CalcCount CalcRefMode CalcIter CalcDelta CalcSaveRecalc PrintRowCol
    #PrintGrid GridSet Guts DefaultRowHeight WsBool [Sync] [LPr] [HorizontalPageBreaks]
    #[VerticalPageBreaks]
    PARSER = Group('globals', Req(CalcMode() << Req(CalcCount()) << Req(CalcRefMode()) << 
                Req(CalcIter()) << Req(CalcDelta()) << Req(CalcSaveRecalc()) << 
                Req(PrintRowCol()) << Req(PrintGrid()) << Req(GridSet()) << Req(Guts()) <<
                Req(DefaultRowHeight()) << Req(WsBool()) << Sync() << LPr() << 
                HorizontalPageBreaks() << VerticalPageBreaks()))

class BIGNAME(BaseParser): pass

class DefColWidth(BaseParser):
    PARSER = Term(xlsrecord.DefColWidth)

class ColInfo(BaseParser): pass

class COLUMNS(BaseParser):
    # COLUMNS = DefColWidth *255ColInfo
    PARSER = Group('columns', Req(DefColWidth()) << Many('columns-list', ColInfo(), max=255))

class SCENARIOS(BaseParser): pass

class Sort(BaseParser): pass
class SORTDATA12(BaseParser): pass
class FilterMode(BaseParser): pass
class DropDownObjIds(BaseParser): pass
class AUTOFILTER(BaseParser): pass

class SORTANDFILTER(BaseParser): 
    # SORTANDFILTER = [Sort] [SORTDATA12] [FilterMode] [DropDownObjIds] [AUTOFILTER]
    PARSER = Group('sort-and-filter', Sort() << Opt(SORTDATA12()) << FilterMode() << DropDownObjIds() << Opt(AUTOFILTER()))

class Row(BaseParser):
    PARSER = Term(xlsrecord.Row)

class FORMULA(BaseParser): pass
class Blank(BaseParser): pass

class MulBlank(BaseParser):
    PARSER = Term(xlsrecord.MulBlank)

class Rk(BaseParser):
    PARSER = Term(xlsrecord.RK)

class MulRk(BaseParser): pass
class BoolErr(BaseParser): pass
class Number(BaseParser): pass

class LabelSst(BaseParser):
    PARSER = Term(xlsrecord.LabelSST)

class CELL(BaseParser): 
    #CELL = FORMULA / Blank / MulBlank / RK / MulRk / BoolErr / Number / LabelSst
    PARSER = OneOf(FORMULA(), Blank(), MulBlank(), Rk(), MulRk(), BoolErr(), Number(), LabelSst())

class DBCell(BaseParser):
    PARSER = Term(xlsrecord.DBCell)

class EntExU2(BaseParser): pass

class CELLTABLE(BaseParser): 
    # CELLTABLE = 1*(1*Row *CELL 1*DBCell) *EntExU2
    PARSER = Group('cell-table', Many('rows-groups', 
                                      Group('row-group', 
                                            Many('rows', Row(), min=1) << Many('cells', CELL()) << Many('dbcells', DBCell(), min=1)), 
                                      min=1) << Many('entexu2-list', EntExU2()))

class NoteSh(BaseParser):
    PARSER = Term(xlsrecord.NoteSh)

class PIVOTVIEW(BaseParser): pass
class DCON(BaseParser): pass
class SORT(BaseParser): pass

class DxGCol(BaseParser):
    PARSER = Term(xlsrecord.DxGCol)

class MergeCells(BaseParser):
    PARSER = Term(xlsrecord.MergeCells)

class LRng(BaseParser): pass
class QUERYTABLE(BaseParser): pass

class PhoneticInfo(BaseParser):
    PARSER = Term(xlsrecord.PhoneticInfo)

class PHONETICINFO(BaseParser):
    # PHONETICINFO = PhoneticInfo *Continue
    PARSER = Group('phonetic-info-group', Req(PhoneticInfo()) << Many('conitnues', Continue()))

class CONDFMT(BaseParser): pass
class CONDFMT12(BaseParser): pass
class CFEx(BaseParser): pass
class CF12(BaseParser): pass

class CONDFMTS(BaseParser):
    # CONDFMTS = *(CONDFMT / CONDFMT12) *(CFEx [CF12])
    PARSER = Group('condfmts', Many('condfmt-list', OneOf(CONDFMT(), CONDFMT12())) << Many('cf-list', Req(CFEx()) << CF12()))

class HLINK(BaseParser): pass
class DVAL(BaseParser): pass
class CellWatch(BaseParser): pass
class FEAT(BaseParser): pass
class FEAT11(BaseParser): pass
class RECORD12(BaseParser): pass

# NOTE: this is not from the doc
class FUTURES(BaseParser):
    PARSER = Many('futures', OneOf(PLVMac()))

class WORKSHEETCONTENT(BaseParser):
    #WORKSHEETCONTENT = [Uncalced] Index GLOBALS PAGESETUP [HeaderFooter] [BACKGROUND]
    #*BIGNAME [PROTECTION] COLUMNS [SCENARIOS] SORTANDFILTER Dimensions [CELLTABLE]
    #OBJECTS *HFPicture *Note *PIVOTVIEW [DCON] 1*WINDOW *CUSTOMVIEW *2SORT [DxGCol]
    #*MergeCells [LRng] *QUERYTABLE [PHONETICINFO] CONDFMTS *HLINK [DVAL] [CodeName]
    #*WebPub *CellWatch [SheetExt] *FEAT *FEAT11 *RECORD12 EOF
    PARSER = Group('worksheet-content', Uncalced() << Req(Index()) << Req(GLOBALS()) << 
                Req(PAGESETUP()) << HeaderFooter() << Opt(BACKGROUND()) << Many('big-names', BIGNAME())
                << Opt(PROTECTION()) << Req(COLUMNS()) << Opt(SCENARIOS()) << Req(SORTANDFILTER()) <<
                Req(Dimensions()) << Opt(CELLTABLE()) << Req(OBJECTS()) << Many('hfpictures', HFPicture()) <<
                Many('notes', NoteSh()) << Many('pivot-views', PIVOTVIEW()) << Opt(DCON()) <<
                Many('windows', WINDOW(), min=1) << Many('custom-views', CUSTOMVIEW()) << 
                Many('sort-list', SORT(), max=2) << DxGCol() << Many('merged-cells-list', MergeCells()) <<
                LRng() << Many('query-tables', QUERYTABLE()) << Opt(PHONETICINFO()) << 
                Req(CONDFMTS()) << Many('hlinks', HLINK()) << Opt(DVAL()) << CodeName() <<
                Many('web-pubs', WebPub()) << Many('cell-watch-list', CellWatch()) << SheetExt() << 
                Many('feat-list', FEAT()) << Many('feat11-list', FEAT11()) << Many('record12-list', RECORD12()) <<
                FUTURES() << Req(EOF()))
    
class XlsParser(BaseParser):
    def __init__(self, tokens):
        self.__tokenStream = TokenStream(tokens)
        
    def parse(self, stream):
        PARSERS = {0x0005: None, # WorkbookGlobal
                   0x0006: None,# Visual Basic module,
                   0x0010: ('worksheet', WORKSHEETCONTENT),# Worksheet
                   0x0020: ('chart', CHARTSHEETCONTENT),
                   0x0040: None,# Excel 4.0 macro sheet
                   0x0100: None,# Workspace file
                   }
        parsedList = []
        bofParser = Req(BOF())
        
        while not stream.eof():
            bof = None
            parser = None
            try:
                bof = safeParse(bofParser, stream)
            except ParseException:
                pass
            if not bof is None: 
                bof.dumpData() # we need to dump data to make it parse the record
                parser = PARSERS[bof.dataType]
            
            try:
                if not parser is None:
                    parsed = (parser[0], parser[1]().parse(stream))
                    parsedList.append(parsed)
                else:
                    parser = Many('any-list', AnyButThis(OneOf(EOF(), BOF()))) << EOF()
                    parsed = parser.parse(stream) # skipping the unknown stream
                    parsedList.append(parsed)
            except ParseException:
                print (
                    "Parse failed, previous token is [%s], next tokens are [%s] the maximum token seq is [%s]"% \
                    (stream.tokens[stream.currentIndex-1], 
                     ','.join(map(str,stream.tokens[stream.currentIndex:stream.currentIndex+5]),),
                     ','.join(map(str,stream.tokens[stream.maxCurrentIndex-4:stream.maxCurrentIndex+1]),)))
                raise
        return parsedList
    
    def __dumpRoot(self, parsed):
        if parsed is None:
            return None
        elif isinstance(parsed, tuple):
            return (parsed[0], self.__dumpRoot(parsed[1]))
        elif isinstance(parsed, list):
            return map(self.__dumpRoot, parsed)
        else:
            return parsed.dumpData()
        
    def dumpData(self):
        parsed = self.parse(self.__tokenStream)
        if parsed is None:
            return None
        return self.__dumpRoot(parsed)
        
    
    
