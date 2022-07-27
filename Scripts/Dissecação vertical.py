# -*- coding: cp1252 -*-
# Import system modules
import arcpy, os, random, sys
from arcpy import env
from arcpy.sa import *
import math
from math import hypot
from operator import itemgetter
from operator import add
import collections
from collections import OrderedDict

###Start extendline - Source: http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance
def extendline (layer, distance):

    #Computes new coordinates x3,y3 at a specified distance
    #along the prolongation of the line from x1,y1 to x2,y2
    def newcoord(coords, dist):
        (x1,y1),(x2,y2) = coords
        dx = x2 - x1
        dy = y2 - y1
        linelen = hypot(dx, dy)

        x3 = x2 + dx/linelen * dist
        y3 = y2 + dy/linelen * dist    
        return x3, y3

    #accumulate([1,2,3,4,5]) --> 1 3 6 10 15
    #Equivalent to itertools.accumulate() which isn't present in Python 2.7
    def accumulate(iterable):    
        it = iter(iterable)
        total = next(it)
        yield total
        for element in it:
            total = add(total, element)
            yield total

    #OID is needed to determine how to break up flat list of data by feature.
    coordinates = [[row[0], row[1]] for row in
                   arcpy.da.SearchCursor(layer, ["OID@", "SHAPE@XY"], explode_to_points=True)]

    oid,vert = zip(*coordinates)

    #Construct list of numbers that mark the start of a new feature class.
    #This is created by counting OIDS and then accumulating the values.
    vertcounts = list(accumulate(collections.Counter(oid).values()))

    #Grab the last two vertices of each feature
    lastpoint = [point for x,point in enumerate(vert) if x+1 in vertcounts or x+2 in vertcounts]

    #Convert flat list of tuples to list of lists of tuples.
    #Obtain list of tuples of new end coordinates.
    newvert = [newcoord(y, distance) for y in zip(*[iter(lastpoint)]*2)]    

    j = 0
    with arcpy.da.UpdateCursor(layer, "SHAPE@XY", explode_to_points=True) as rows:
        for i,row in enumerate(rows):
            if i+1 in vertcounts:           
                row[0] = newvert[j]
                j+=1
                rows.updateRow(row)
###End extendline

###START SPLIT LINE CODE IN A SAME DISTANCE### Source: http://nodedangles.wordpress.com/2011/05/01/quick-dirty-arcpy-batch-splitting-polylines-to-a-specific-length/
def splitline (inFC,FCName,alongDist):

    OutDir = env.workspace
    outFCName = FCName
    outFC = OutDir+"/"+outFCName
    
    def distPoint(p1, p2):
        calc1 = p1.X - p2.X
        calc2 = p1.Y - p2.Y

        return math.sqrt((calc1**2)+(calc2**2))

    def midpoint(prevpoint,nextpoint,targetDist,totalDist):
        newX = prevpoint.X + ((nextpoint.X - prevpoint.X) * (targetDist/totalDist))
        newY = prevpoint.Y + ((nextpoint.Y - prevpoint.Y) * (targetDist/totalDist))
        return arcpy.Point(newX, newY)

    def splitShape(feat,splitDist):
        # Count the number of points in the current multipart feature
        #
        partcount = feat.partCount
        partnum = 0
        # Enter while loop for each part in the feature (if a singlepart feature
        # this will occur only once)
        #
        lineArray = arcpy.Array()

        while partnum < partcount:
              # Print the part number
              #
              #print "Part " + str(partnum) + ":"
              part = feat.getPart(partnum)
              #print part.count

              totalDist = 0

              pnt = part.next()
              pntcount = 0

              prevpoint = None
              shapelist = []

              # Enter while loop for each vertex
              #
              while pnt:

                    if not (prevpoint is None):
                        thisDist = distPoint(prevpoint,pnt)
                        maxAdditionalDist = splitDist - totalDist

                        #print thisDist, totalDist, maxAdditionalDist

                        if (totalDist+thisDist)> splitDist:
                              while(totalDist+thisDist) > splitDist:
                                    maxAdditionalDist = splitDist - totalDist
                                    #print thisDist, totalDist, maxAdditionalDist
                                    newpoint = midpoint(prevpoint,pnt,maxAdditionalDist,thisDist)
                                    lineArray.add(newpoint)
                                    shapelist.append(lineArray)

                                    lineArray = arcpy.Array()
                                    lineArray.add(newpoint)
                                    prevpoint = newpoint
                                    thisDist = distPoint(prevpoint,pnt)
                                    totalDist = 0

                              lineArray.add(pnt)
                              totalDist+=thisDist
                        else:
                              totalDist+=thisDist
                              lineArray.add(pnt)
                              #shapelist.append(lineArray)
                    else:
                        lineArray.add(pnt)
                        totalDist = 0

                    prevpoint = pnt                
                    pntcount += 1

                    pnt = part.next()

                    # If pnt is null, either the part is finished or there is an
                    #   interior ring
                    #
                    if not pnt:
                        pnt = part.next()
                        if pnt:
                              print "Interior Ring:"
              partnum += 1

        if (lineArray.count > 1):
              shapelist.append(lineArray)

        return shapelist

    if arcpy.Exists(outFC):
        arcpy.Delete_management(outFC)

    arcpy.Copy_management(inFC,outFC)

    #origDesc = arcpy.Describe(inFC)
    #sR = origDesc.spatialReference

    #revDesc = arcpy.Describe(outFC)
    #revDesc.ShapeFieldName

    deleterows = arcpy.UpdateCursor(outFC)
    for iDRow in deleterows:       
         deleterows.deleteRow(iDRow)

    try:
        del iDRow
        del deleterows
    except:
        pass

    inputRows = arcpy.SearchCursor(inFC)
    outputRows = arcpy.InsertCursor(outFC)
    fields = arcpy.ListFields(inFC)

    numRecords = int(arcpy.GetCount_management(inFC).getOutput(0))
    OnePercentThreshold = numRecords // 100

    #printit(numRecords)

    iCounter = 0
    iCounter2 = 0

    for iInRow in inputRows:
        inGeom = iInRow.shape
        iCounter+=1
        iCounter2+=1    
        if (iCounter2 > (OnePercentThreshold+0)):
              #printit("Processing Record "+str(iCounter) + " of "+ str(numRecords))
              iCounter2=0

        if (inGeom.length > alongDist):
              shapeList = splitShape(iInRow.shape,alongDist)

              for itmp in shapeList:
                    newRow = outputRows.newRow()
                    for ifield in fields:
                        if (ifield.editable):
                              newRow.setValue(ifield.name,iInRow.getValue(ifield.name))
                    newRow.shape = itmp
                    outputRows.insertRow(newRow)
        else:
              outputRows.insertRow(iInRow)

    del inputRows
    del outputRows

    #printit("Done!")
###END SPLIT LINE CODE IN A SAME DISTANCE###

#Set environments
arcpy.env.overwriteOutput = True
arcpy.env.XYResolution = "0.00001 Meters"
arcpy.env.XYTolerance = "0.0001 Meters"

# Check out the ArcGIS extension license
arcpy.CheckOutExtension("Spatial")
arcpy.CheckOutExtension('3D')
  
# Set local variables
WorkFolder=arcpy.GetParameterAsText(0)
Stream=arcpy.GetParameterAsText(1)
Basins_input=arcpy.GetParameterAsText(2)
Contour_input=arcpy.GetParameterAsText(3)
ContourInterval_par=float(arcpy.GetParameterAsText(4))
ContourElevField=arcpy.GetParameterAsText(5)
DEM=arcpy.GetParameterAsText(6)
Scale=arcpy.GetParameterAsText(7)
DissecOut_location=arcpy.GetParameterAsText(8)
DissecOut_name=arcpy.GetParameterAsText(9)

#Define Scale_par, SplitStream_par and BufferStream_par, DensifyBasin_par
Scale_par=int((Scale.split(":"))[1])/5000
SplitStream_par=Scale_par
BufferStream_par=str(Scale_par*5)
DensifyBasin_par="%d Meters" %Scale_par

#Set a folder as Workspace
env.workspace=WorkFolder

# Prepare fodler to Work #
## List all file geodatabases in the current workspace
workspaces=arcpy.ListWorkspaces("*", "FileGDB")
## Delete each geodatabase
for workspace in workspaces:
    arcpy.Delete_management(workspace)
arcpy.SetParameterAsText(1, "true")

## Create "General" file geodatabase
General_GDB=WorkFolder+"\General.gdb"
arcpy.CreateFileGDB_management(WorkFolder, "General", "CURRENT")
env.workspace=WorkFolder+"\General.gdb"

# Process Stream #
## Export Stream to "General" geodatabase
StreamFlip=General_GDB+"\StreamFlip"
arcpy.FeatureClassToFeatureClass_conversion(Stream, General_GDB, "StreamFlip", "", "", "")

## Flip Stream
arcpy.FlipLine_edit(StreamFlip)

#Prepare DEM
DEM_R=General_GDB+"\Dem_R"
arcpy.Resample_management(DEM, DEM_R, "0.5", "NEAREST")
arcpy.MakeRasterLayer_management (DEM_R, "DEM_R_layer")

#Processing Basins
## Export Basins to "General" geodatabase
Basins=General_GDB+"\Basins"
arcpy.FeatureClassToFeatureClass_conversion(Basins_input, General_GDB, "Basins", "", "", "")
##Calculate Z_min and Z_max for all bassins
###Add Fields (z_min and z_max)
arcpy.MakeFeatureLayer_management(Basins, "Basins_layer")
arcpy.AddField_management ("Basins_layer", "z_min", "LONG")
arcpy.AddField_management ("Basins_layer", "z_max", "LONG")
###Calculate Elev statistic table
MinMax_tab=General_GDB+"\MinMax_tab"
outZSaT=ZonalStatisticsAsTable ("Basins_layer", "OBJECTID", "DEM_R_layer", MinMax_tab, "NODATA", "MIN_MAX")
arcpy.MakeTableView_management (MinMax_tab, "MinMax_tab_view")
###Add join
arcpy.AddJoin_management ("Basins_layer", "OBJECTID", "MinMax_tab_view", "OBJECTID_1")
###Calculate fields
arcpy.CalculateField_management ("Basins_layer", "z_min", "[MinMax_tab.MIN]", "VB", "")
arcpy.CalculateField_management ("Basins_layer", "z_max", "[MinMax_tab.MAX]", "VB", "")
###Remove join
arcpy.RemoveJoin_management ("Basins_layer")

#Make Unsplit and make contour Layer
Contour=General_GDB+"\Contour"
arcpy.UnsplitLine_management (Contour_input, Contour, ContourElevField)
arcpy.MakeFeatureLayer_management (Contour, "Contour_layer")

#Create Basins List#
##Create direct list (Basins_list)
rows_Basins=arcpy.SearchCursor (Basins)
Basins_list = []
for row in rows_Basins:
    value = str(row.getValue("OBJECTID"))
    Basins_list.append(value)

NC_dissec=0

# Processing each Basin #
len_BasinsList=len(Basins_list)
##Loop Basins
for rowB in Basins_list:
    #Set Basins extend
    descbasins=arcpy.Describe(Basins)
    arcpy.env.extent=descbasins.extent    

    #Get a basin ID
    Basin_ID=int(rowB)
    Basin_Name="B%d"%Basin_ID
    arcpy.AddMessage("Processando Bacia %d/%d "%(Basin_ID, len_BasinsList))

    #Create a Geodatabase
    arcpy.CreateFileGDB_management (WorkFolder, Basin_Name, "CURRENT")

    #Set geodatabase as Workspace
    env.workspace=("%s\%s.gdb" % (WorkFolder, Basin_Name))
    
    #Export a basin
    expressionBasin = '"OBJECTID" ='+str(Basin_ID)
    Basin_S="B_%d"%Basin_ID
    arcpy.FeatureClassToFeatureClass_conversion("Basins_layer", env.workspace,  Basin_S, expressionBasin)
    arcpy.MakeFeatureLayer_management (Basin_S, "Basin_S_layer")

    #Basin buffer and set basin extend
    BasinBuffer="in_memory\B%d_100"%Basin_ID
    BasinBuffer_05="in_memory\B%d_100"%Basin_ID
    arcpy.Buffer_analysis(Basin_S, BasinBuffer, "100 Meters", "FULL")
    arcpy.Buffer_analysis(Basin_S, BasinBuffer_05, "0.5 Meters", "FULL")                  
    descbasin=arcpy.Describe(BasinBuffer)
    arcpy.env.extent=descbasin.extent

    #Procensing stream Part 1#
    ##Clip stream
    StreamClip="Stream_B%d"%Basin_ID
    arcpy.Clip_analysis(StreamFlip, Basin_S, StreamClip, "")
    ##Dissolve stream
    StreamDissolve="StreamDissolve_B%d"%Basin_ID
    arcpy.Dissolve_management (StreamClip, StreamDissolve,"", "", "SINGLE_PART")
    ##Buffer stream
    Stream_buffer2m = "in_memory\Stream_buffer2m_B%d"%Basin_ID
    arcpy.Buffer_analysis(StreamClip, Stream_buffer2m, "2 Meters", "FULL", "ROUND", "NONE", "")
    
    #Processing basin and basin points#
    ##Densify basin
    BasinDensify="B%d_Densify"%Basin_ID
    arcpy.Copy_management(Basin_S, BasinDensify,"")
    arcpy.Densify_edit(BasinDensify, "DISTANCE", DensifyBasin_par)
    ##Basin to line
    BasinLine="in_memory\B%d_Line"%Basin_ID
    BasinBuffer_05_line="in_memory\B%d_05_line"%Basin_ID    
    arcpy.FeatureToLine_management([BasinDensify], BasinLine)
    arcpy.FeatureToLine_management([BasinBuffer_05], BasinBuffer_05_line)
    ##Delete the both ends points of basin
    Stream_EndsPoint = "in_memory\StreamEnds_B%d"%Basin_ID
    arcpy.FeatureVerticesToPoints_management(StreamDissolve, Stream_EndsPoint, "BOTH_ENDS")
    StreamEnds_buffer="in_memory\StreamEndsBuffer_B%d"%Basin_ID
    arcpy.Buffer_analysis(Stream_EndsPoint, StreamEnds_buffer, "1 Meters", "FULL", "ROUND", "NONE", "")
    BasinLine_erase = "in_memory\B%d_LineErase"%Basin_ID
    arcpy.Erase_analysis(BasinLine, StreamEnds_buffer, BasinLine_erase)
    BasinLine_dissolve="in_memory\B%d_LineDissolve"%Basin_ID
    arcpy.Dissolve_management(BasinLine_erase, BasinLine_dissolve, "", "", "SINGLE_PART", "DISSOLVE_LINES")
    ##Generate Basin Point
    BasinPoints = "in_memory\B%d_point"%Basin_ID
    arcpy.FeatureVerticesToPoints_management(BasinLine_dissolve, BasinPoints, "ALL")
    ##Add XY field and delete overlap points
    arcpy.AddXY_management(BasinPoints)
    arcpy.DeleteIdentical_management(BasinPoints, "POINT_X;POINT_Y", "", "0")
    ##Calculate BasinPtElev statistic table
    arcpy.MakeFeatureLayer_management(BasinPoints, "BasinPoints_layer")
    BasinPtElev_tab="in_memory\BasinPtElev_tab"
    outZSaT=ZonalStatisticsAsTable ("BasinPoints_layer", "OBJECTID", "DEM_R_layer", BasinPtElev_tab, "NODATA", "MAXIMUM")
    arcpy.MakeTableView_management (BasinPtElev_tab, "BasinPtElev_tab_view")
    ##Get Min a Max elevation of the basin
    basin_rows = arcpy.SearchCursor (Basin_S)
    basin_row = basin_rows.next()
    Basin_MinElev=int(basin_row.getValue("z_min"))
    Basin_MaxElev=int(basin_row.getValue("z_max"))

    #Clip contour
    ContourClip="in_memory\Contour_B%d"%Basin_ID
    arcpy.Clip_analysis(Contour, Basin_S, ContourClip, "")
    

    #Processing Stream Part 2#
    ##Split stream
    SplitStream="SplitStre_B%d" %Basin_ID
    splitline(StreamDissolve,SplitStream, SplitStream_par)
    ##Add and calculate Azimuth field for SplitStream
    arcpy.AddField_management(SplitStream, "azimuth", "Double", "", "", "", "", "NULLABLE")
    codeblock = """def CalculaAzimuth(linea):
        if (hasattr(linea,'type') and linea.type == 'polyline'):
            xf = linea.firstPoint.X
            yf = linea.firstPoint.Y
            xl = linea.lastPoint.X
            yl = linea.lastPoint.Y
            dX = xl - xf
            dY = yl - yf
            PI = math.pi
            Azimuth = 0 #Default case, dX = 0 and dY >= 0
            if dX > 0:
                Azimuth = 90 - math.atan( dY / dX ) * 180 / PI
            elif dX < 0:
                Azimuth = 270 - math.atan( dY / dX )* 180 / PI
            elif dY < 0:
                Azimuth = 180
            return Azimuth
        else:
            return False"""
    arcpy.CalculateField_management(SplitStream,"azimuth",'CalculaAzimuth(!shape!)','PYTHON_9.3', codeblock)
    ##Calculate Maximum Elevation for SplitStream Segments
    ###Add Field (z_max)
    arcpy.MakeFeatureLayer_management(SplitStream, "SplitStream_layer")
    arcpy.AddField_management ("SplitStream_layer", "z_max", "LONG")
    ###Calculate SplitStream_Maxtab
    SplitStream_Maxtab="SplitStream_Maxtab"
    outZSaT=ZonalStatisticsAsTable ("SplitStream_layer", "OBJECTID", "DEM_R_layer", SplitStream_Maxtab, "NODATA", "MAXIMUM")
    arcpy.MakeTableView_management ("SplitStream_Maxtab", "SplitStream_Maxtab_view")
    ###Add join
    arcpy.AddJoin_management ("SplitStream_layer", "OBJECTID", "SplitStream_Maxtab_view", "OBJECTID_1")
    ###Calculate field
    arcpy.CalculateField_management ("SplitStream_layer", "z_max", "[SplitStream_Maxtab.MAX]", "VB", "")
    ###Remove join
    arcpy.RemoveJoin_management ("SplitStream_layer")

    ##Select Mid stream Segments
    arcpy.SelectLayerByLocation_management("SplitStream_layer", '', "", "", "SWITCH_SELECTION")
    arcpy.SelectLayerByLocation_management("SplitStream_layer", 'intersect', Stream_EndsPoint, "", "REMOVE_FROM_SELECTION")
    ##Calculate disntace to Basin border
    arcpy.Near_analysis("SplitStream_layer", BasinLine)
    ##Select SplitStream Segments with distance Less than 0.5 meter
    arcpy.SelectLayerByAttribute_management("SplitStream_layer", "SUBSET_SELECTION", 'NEAR_DIST < 0.5')

    ##Generate StreamPointsMulti using "intersection tools"
    StreamPoints_Multi="StreamPointsMulti_B%d"%Basin_ID
    arcpy.Intersect_analysis ([ContourClip, SplitStream], StreamPoints_Multi, "ALL", "", "POINT")
    StreamPoints_count=arcpy.GetCount_management(StreamPoints_Multi)
    StreamPoints_count=int(StreamPoints_count.getOutput(0))
    if StreamPoints_count==0:
        ##Generate MID stream points
        Stream_MidPoints="in_memory\Stream_MidPoints"
        arcpy.FeatureVerticesToPoints_management(StreamDissolve, Stream_MidPoints, "MID")
        
    if StreamPoints_count>0:
        ##Create StreamPoint and convert multipoint to point
        StreamPoints="StreamPointsB%d"%Basin_ID
        arcpy.MultipartToSinglepart_management (StreamPoints_Multi, StreamPoints)

        ##Generate MID stream points
        Stream_SlitAtPoints1="in_memory\StreamAtSlitPoints1"
        arcpy.SplitLineAtPoint_management (StreamDissolve, StreamPoints, Stream_SlitAtPoints1, 0.1)
        Stream_SlitAtPoints2="in_memory\StreamAtSlitPoints2"
        arcpy.SplitLineAtPoint_management (Stream_SlitAtPoints1, "BasinPoints_layer", Stream_SlitAtPoints2, 0.1)
        Stream_MidPoints="in_memory\Stream_MidPoints"
        arcpy.FeatureVerticesToPoints_management(Stream_SlitAtPoints2, Stream_MidPoints, "MID")
        
        #Create Dissection lines StreamPoints Buffer
        spatial_reference = arcpy.Describe(Basin_S).spatialReference
        arcpy.CreateFeatureclass_management(env.workspace, "DissecLines_L", "POLYLINE", "", "", "", spatial_reference)
        arcpy.CreateFeatureclass_management(env.workspace, "DissecLines_R", "POLYLINE", "", "", "", spatial_reference)
        arcpy.CreateFeatureclass_management(env.workspace, "DissecLines_L_temp", "POLYLINE", "", "", "", spatial_reference)
        arcpy.CreateFeatureclass_management(env.workspace, "DissecLines_R_temp", "POLYLINE", "", "", "", spatial_reference)
        arcpy.CreateFeatureclass_management(env.workspace, "Contour_PointSegs", "POLYLINE", "", "", "", spatial_reference)
        DissecLines_L="DissecLines_L"
        DissecLines_R="DissecLines_R"
        DissecLines_L_temp="DissecLines_L_temp"
        DissecLines_R_temp="DissecLines_R_temp"       
        Contour_PointSegs="Contour_PointSegs"

        #Create layers StreamPoints and BasinPoints layers
        arcpy.MakeFeatureLayer_management(StreamPoints, "StreamPoints_layer")

        #Create StreamPoints List#
        ##Generate Cursors
        rows_StreamPoints=sorted(arcpy.da.SearchCursor(StreamPoints, ContourElevField))
        rows_SplitStream=sorted(arcpy.da.SearchCursor("SplitStream_layer", "z_max"))
        #Definig StreamPoints_list
        StreamPoints_list = []
        ##Populate StreamPoints_list
        if len(rows_SplitStream)>0:
            StreamPoints_values = []
            for value in rows_StreamPoints:
                StreamPoints_values.append (int(value[0]))
           
            n=1
            while (len(rows_SplitStream)+1)>=n:
                if n==1:
                    listP=[]
                    for value in StreamPoints_values:
                        if value<=rows_SplitStream[0][0]:
                            listP.append(value)
                if n==(len(rows_SplitStream)+1):
                    listP=[]
                    for value in StreamPoints_values:
                        if value>rows_SplitStream[n-2][0]:
                            listP.append(value)
                if n>1 and n<=len(rows_SplitStream):
                    listP=[]
                    for value in StreamPoints_values:
                        if value>rows_SplitStream[n-2][0] and value<=rows_SplitStream[n-1][0]:
                            listP.append(value)
                ##StreamPoints_list
                listP_corect=[]
                len_list=len(listP)
                for e, pt in enumerate (listP):
                    if e<len_list-(e+1):
                        listP_corect.append(str(listP[e]))
                        listP_corect.append(str(listP[len_list-(e+1)]))
                        continue
                    if e==len_list-(e+1):
                        listP_corect.append(str(listP[e]))
                        break
                    else:
                        break
                listP=listP_corect
                for row in listP:
                    StreamPoints_list.append(row)
                n+=1
            #Remove duplicate values 
            StreamPoints_list=list(list(OrderedDict.fromkeys(StreamPoints_list).keys()))
        else:
            for row in rows_StreamPoints:
                StreamPoints_list.append(int(row[0]))
            ##Invert StreamPoints_list
            StreamPoints_List_corect=[]
            len_list=len(StreamPoints_list)
            for e, pt in enumerate (StreamPoints_list):
                if e<len_list-(e+1):
                    StreamPoints_List_corect.append(str(StreamPoints_list[e]))
                    StreamPoints_List_corect.append(str(StreamPoints_list[len_list-(e+1)]))
                    continue
                if e==len_list-(e+1):
                    StreamPoints_List_corect.append(str(StreamPoints_list[e]))
                    break
                else:
                    break
            StreamPoints_list=StreamPoints_List_corect
        #arcpy.AddMessage(StreamPoints_list)
        

        ###Start Processing each Stream Point###
        n=0
        len_StreamPointsList=len(StreamPoints_list)
        #Loop StreamPoints_list
        for row in StreamPoints_list:
            n+=1
            # Make a pt_select layer    
            expressionE = '%s=%s'%(ContourElevField, row)
            arcpy.MakeFeatureLayer_management ("StreamPoints_layer", "Stream_Points", expressionE)
            StreamPoints_elements=arcpy.da.SearchCursor("Stream_Points", "OBJECTID")
            for element in StreamPoints_elements:
                #Get id ptdrena
                StreamPoint_ID=str(element[0])
                #Make a pt_select layer Buffer
                expressionS = '%s=%s'%("OBJECTID", StreamPoint_ID)
                arcpy.MakeFeatureLayer_management ("StreamPoints_layer", "Stream_Point", expressionS)
                StreamPoint_Buffer="in_memory\StreamPt%s_Buffer"%StreamPoint_ID
                arcpy.Buffer_analysis("Stream_Point", StreamPoint_Buffer,  BufferStream_par, "FULL", "ROUND", "NONE", "")
                StreamPoint_Buffer_05="in_memory\StreamPt%s_Buffer05"%StreamPoint_ID
                arcpy.Buffer_analysis("Stream_Point", StreamPoint_Buffer_05, "0.1", "FULL", "ROUND", "NONE", "")
                #Select contour
                arcpy.SelectLayerByLocation_management("Contour_layer", 'intersect', "Stream_Point", "0.1", "NEW_SELECTION")
                #Clip Contour and append
                Contour_PointSeg="in_memory\Contour_Point%sSeg"%StreamPoint_ID
                arcpy.Clip_analysis("Contour_layer", StreamPoint_Buffer, Contour_PointSeg)
                arcpy.Append_management ([Contour_PointSeg], Contour_PointSegs, "NO_TEST")

                #Processing StreamPoint_Buffer#
                ##Convert StreamPoint Buffer to line
                StreamPoint_PTLine="in_memory\StreamPointPT%s_BLine"%StreamPoint_ID
                arcpy.PolygonToLine_management(StreamPoint_Buffer, StreamPoint_PTLine, "IGNORE_NEIGHBORS")
                ##Convert StreamPoints PTLine and Contour to polygon
                StreamPoint_PTSplit="in_memory\StreamPointPT%s_Split"%StreamPoint_ID
                arcpy.FeatureToPolygon_management([StreamPoint_PTLine,Contour_PointSeg],  StreamPoint_PTSplit, "","NO_ATTRIBUTES", "")
                arcpy.MakeFeatureLayer_management (StreamPoint_PTSplit, "StreamPoint_PTSplit_layer")
                ##Clip StreamDissolve with StreamPoint_PTSplit
                StreamClip_point="in_memory\StreamClip_PT%s"%StreamPoint_ID
                arcpy.Clip_analysis(StreamDissolve, StreamPoint_PTSplit, StreamClip_point, "")
                ##Convert StreamClip_point to point
                StreamClip_PtFirst="in_memory\StreamClip_Pt%sFirst"%StreamPoint_ID
                arcpy.FeatureVerticesToPoints_management(StreamClip_point, StreamClip_PtFirst, "START")
                ##Select StreamPoint_PTSplit polygon
                arcpy.SelectLayerByLocation_management("StreamPoint_PTSplit_layer", 'intersect', StreamClip_PtFirst, "", "NEW_SELECTION")
                arcpy.MakeFeatureLayer_management ("StreamPoint_PTSplit_layer", "LowSector_layer")
                arcpy.SelectLayerByLocation_management("StreamPoint_PTSplit_layer", '', "", "", "SWITCH_SELECTION")
                arcpy.MakeFeatureLayer_management ("StreamPoint_PTSplit_layer", "HighSector_layer")
                ##Generate LowSector_line
                LowSector_line="in_memory\LowSector_line"
                arcpy.Erase_analysis (StreamPoint_PTLine, "HighSector_layer", LowSector_line, "0.1")

                #Erase Contour and Stream
                ContourErase="in_memory\ContourErase_pt%s"%StreamPoint_ID
                arcpy.Erase_analysis(ContourClip, StreamPoint_Buffer, ContourErase)
                Stream_Erasept="in_memory\StreamErase_pt%s"%StreamPoint_ID
                arcpy.Erase_analysis(StreamDissolve,StreamPoint_Buffer_05, Stream_Erasept)
                       
                # Get Stream_Point Elevation and Azimuth#
                dir_rows = arcpy.SearchCursor ("Stream_Point")
                dir_row = dir_rows.next()
                ##Get direction
                dir_Stream_Point = int(dir_row.getValue("azimuth"))
                ##Get elevation
                elev_Stream_Point=int(dir_row.getValue(ContourElevField))

                #Select low contours
                expression_Contour='%s<=%d'% (ContourElevField, elev_Stream_Point)
                arcpy.MakeFeatureLayer_management (ContourErase, "ContourLow_layer", expression_Contour)

                #Create expression#
                a=10
                ##Expression expression_leftlines#
                LimitL_min = dir_Stream_Point + a
                if LimitL_min > 360:
                    LimitL_min-=360
                LimitL_max = LimitL_min + (180 - a)
                if LimitL_max<=360:
                    expression_leftlines = 'AZIMUTH > %s and AZIMUTH <= %s'% (LimitL_min, LimitL_max)
                elif LimitL_max>360:
                    LimitL_max-=360
                    expression_leftlines = 'AZIMUTH > %s OR AZIMUTH <= %s'% (LimitL_min, LimitL_max)
                ##Expression expression_rightlines
                LimitR_min = dir_Stream_Point - a
                if LimitR_min < 0:
                    LimitR_min+=360
                LimitR_max = LimitR_min - (180 - a)
                if LimitR_max>=0:
                    expression_rightlines = 'AZIMUTH > %s and AZIMUTH <= %s'% (LimitR_max, LimitR_min)
                elif LimitR_max<0:
                    LimitR_max+=360
                    expression_rightlines = 'AZIMUTH > %s OR AZIMUTH <= %s'% (LimitR_max, LimitR_min)

                #Build and select Sightline#
                ##Build Sightlines
                sightlines = "in_memory\sightlines_pt"+StreamPoint_ID
                sample_distance=0.5
                arcpy.ddd.ConstructSightLines("Stream_Point", "BasinPoints_layer", sightlines, "<None>", "<None>", "<None>", sample_distance, "OUTPUT_THE_DIRECTION")
                arcpy.MakeFeatureLayer_management (sightlines, "sightlines_layer")

                ##Add Target elevation Fields to sightlines
                arcpy.AddField_management ("sightlines_layer", "ElevTarg", "Double")
                ##Add join Sightlines with Basin Points
                arcpy.AddJoin_management ("sightlines_layer", "OID_TARGET", "BasinPtElev_tab_view", "OBJECTID_1")
                ##Calculate ElevTarg field
                arcpy.CalculateField_management ("sightlines_layer", "ElevTarg", "[BasinPtElev_tab.MAX]", "VB", "")
                ##Remove join from sightlines_layer
                arcpy.RemoveJoin_management ("sightlines_layer")
                ##Select Sightlines with elevation >= Stream_Point elevation
                expressionSightlines='ElevTarg >= %s'% str(elev_Stream_Point)
                arcpy.MakeFeatureLayer_management (sightlines, "sightlines_layer", expressionSightlines)
                       
                ###Spatial Query### part 1
                arcpy.SelectLayerByLocation_management("sightlines_layer", '', "", "", "SWITCH_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', DissecLines_L_temp, "0.1", "REMOVE_FROM_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', DissecLines_R_temp, "0.1", "REMOVE_FROM_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', BasinBuffer_05_line, "0.1", "REMOVE_FROM_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', "ContourLow_layer", "0.1", "REMOVE_FROM_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', LowSector_line, "0.1", "REMOVE_FROM_SELECTION")
                arcpy.SelectLayerByLocation_management("sightlines_layer", 'intersect', Stream_Erasept, "0.05", "REMOVE_FROM_SELECTION")

                ###Atribute Left Query### part2
                #Build Left Sightlines apling expression_leftline to select left lines
                arcpy.MakeFeatureLayer_management ("sightlines_layer", "sightlinesLR_layer")
                sightlines_SelectedL = "sightline_pt"+StreamPoint_ID+"_S_L"
                arcpy.SelectLayerByAttribute_management("sightlinesLR_layer", "NEW_SELECTION", expression_leftlines)
                #Export Left Sightlines Selection
                arcpy.FeatureClassToFeatureClass_conversion("sightlinesLR_layer", env.workspace, sightlines_SelectedL)
          
                ###Atribute Right Query### part2
                #Build Right Sightlines apling expression_rightlinese to select right lines
                sightlines_SelectedR = "sightline_pt"+StreamPoint_ID+"_S_R"
                arcpy.SelectLayerByAttribute_management("sightlinesLR_layer", "NEW_SELECTION", expression_rightlines)
                #Export Right Sightlines Selection            
                arcpy.FeatureClassToFeatureClass_conversion("sightlinesLR_layer", env.workspace, sightlines_SelectedR)

                ###START - Select the best sightlines###
                #Select Best left line
                lenght_cursor_left = sorted(arcpy.da.SearchCursor(sightlines_SelectedL, ["Shape_Length", "OBJECTID"]))
                if len(lenght_cursor_left)>0:
                    Add_L=True
                    Lenght_left=lenght_cursor_left[0][0]
                    m_rowID = lenght_cursor_left[0][1]
                    #classL = CalcClass(lenght_left)
                    m_rowID = "%d" % m_rowID
                    expressionF = 'OBJECTID ='+ m_rowID
                    arcpy.MakeFeatureLayer_management (sightlines_SelectedL, "sightlineL_select", expressionF)
                    arcpy.Append_management("sightlineL_select", DissecLines_L_temp, "NO_TEST")
                    DissecLines_L_erase="in_memory\DissecLines_L_erase"
                    arcpy.Erase_analysis("sightlineL_select", "LowSector_layer", DissecLines_L_erase)
                    arcpy.Append_management (DissecLines_L_erase, DissecLines_L, "NO_TEST", "", "")
                #Select Best Right line
                lenght_cursor_right = sorted(arcpy.da.SearchCursor(sightlines_SelectedR, ["Shape_Length", "OBJECTID"]))
                if len(lenght_cursor_right)>0:
                    Add_R=True
                    Lenght_right=lenght_cursor_right[0][0]
                    m_rowID = lenght_cursor_right[0][1]
                    m_rowID = "%d" % m_rowID
                    expressionF = 'OBJECTID ='+ m_rowID
                    arcpy.MakeFeatureLayer_management (sightlines_SelectedR, "sightlineR_select", expressionF)
                    arcpy.Append_management("sightlineR_select", DissecLines_R_temp, "NO_TEST")
                    DissecLines_R_erase="in_memory\DissecLines_R_erase"
                    arcpy.Erase_analysis("sightlineR_select", "LowSector_layer", DissecLines_R_erase)
                    arcpy.Append_management (DissecLines_R_erase, DissecLines_R, "NO_TEST")
                #Delete memory files
                try:
                    arcpy.Delete_management(StreamPoint_Buffer)
                    arcpy.Delete_management(StreamPoint_Buffer_05)
                    arcpy.Delete_management(StreamPoint_PTLine)
                    arcpy.Delete_management(StreamPoint_PTSplit)
                    arcpy.Delete_management(StreamClip_point)
                    arcpy.Delete_management(StreamClip_PtFirst)
                    arcpy.Delete_management(ContourErase)
                    arcpy.Delete_management(Stream_Erasept)
                    arcpy.Delete_management(sightlines)
                    arcpy.Delete_management(DissecLines_L_erase)
                    arcpy.Delete_management(DissecLines_R_erase)
                except:
                    pass

                ###END - Select the best sightlines###
                arcpy.AddMessage("Ponto %d/%d OK!"%(n, len_StreamPointsList))
            ###END Processing each Stream Point###
        
    
    arcpy.AddMessage("Calculando a dissecação....")
    # Build Vertical Dissecation pol and Dissecation Zones
    if StreamPoints_count>0:
        #Prepare Contour_PointSegs
        arcpy.MakeFeatureLayer_management (Contour_PointSegs, "Contour_PointSegs_layer")
        arcpy.SelectLayerByLocation_management("Contour_PointSegs_layer", '', "", "", "SWITCH_SELECTION")
        arcpy.SelectLayerByLocation_management("Contour_PointSegs_layer", 'intersect', BasinLine, "", "REMOVE_FROM_SELECTION")
        #Define infeatures
        infeatures_pol = [DissecLines_R, DissecLines_L, StreamClip, Basin_S, ContourClip]
        #infeatures_zones = [DissecLines_R_temp, DissecLines_L_temp, StreamClip, Basin_S, "Contour_PointSegs_layer"]
        infeatures_zones = [DissecLines_R_temp, DissecLines_L_temp, StreamClip, Basin_S]
    else:
        infeatures_pol = [StreamClip, Basin_S, ContourClip]
        infeatures_zones =[StreamClip, Basin_S]
    DissecV_inter = "in_memory\DissecV_inter"
    DissecV_zones = "DissecationV_zones"+str(Basin_ID)
    clusTol = "0.01 Meters"
    arcpy.FeatureToPolygon_management(infeatures_pol, DissecV_inter, clusTol,"NO_ATTRIBUTES", "")
    arcpy.FeatureToPolygon_management(infeatures_zones, DissecV_zones, clusTol,"NO_ATTRIBUTES", "")

    #Calculate Vertical Dissecation#
    ##Add Dissecation Field
    arcpy.AddField_management(DissecV_inter, "DissecationV", "Long", "", "", "", "", "NULLABLE")
    arcpy.MakeFeatureLayer_management (DissecV_inter, "DissecV_inter_layer")
    arcpy.CalculateField_management ("DissecV_inter_layer", "DissecationV", 0, "VB", "")    
    ##Add Zone Field to Dissecation_zones
    arcpy.AddField_management(DissecV_zones, "Zone", "Long", "", "", "", "", "NULLABLE")
    arcpy.MakeFeatureLayer_management (DissecV_zones, "Dissecation_zones_layer")
    arcpy.CalculateField_management ("Dissecation_zones_layer", "Zone", "[OBJECTID]", "VB", "")
 
    #Processing zones
    ##Generate DissecV_point
    DissecV_point="in_memory\DissecV_point"
    arcpy.FeatureToPoint_management ("DissecV_inter_layer", DissecV_point, "INSIDE")
    arcpy.MakeFeatureLayer_management (DissecV_point, "DissecV_point_layer")
    ##Assing zones to points
    DissecV_Zone="in_memory\DissecV_Zone"
    arcpy.SpatialJoin_analysis ("DissecV_point_layer", "Dissecation_zones_layer", DissecV_Zone, "JOIN_ONE_TO_ONE" , "KEEP_ALL", "", "WITHIN", "", "")
    arcpy.MakeFeatureLayer_management (DissecV_Zone, "DissecV_Zone_layer")
    DissecV_pol="DissecationV_B%d"%Basin_ID
    arcpy.SpatialJoin_analysis ("DissecV_inter_layer", "DissecV_Zone_layer", DissecV_pol, "JOIN_ONE_TO_ONE" , "KEEP_ALL", "", "CONTAINS", "", "")
    arcpy.MakeFeatureLayer_management (DissecV_pol, "DissecV_pol_layer")

    ###Calculate first class
    arcpy.MakeFeatureLayer_management(Stream_EndsPoint, "Stream_EndsPoint_layer")
    arcpy.SelectLayerByLocation_management("Stream_EndsPoint_layer", 'INTERSECT', ContourClip, "", "NEW_SELECTION")
    desc=arcpy.Describe("Stream_EndsPoint_layer").FIDSet
    ####If no selection
    if desc!="":
        arcpy.MakeFeatureLayer_management(StreamClip, "StreamClip_layer")
        extendline("StreamClip_layer", 0.5)
        Stream_EndsPoint = "in_memory\StreamEnds_B%d"%Basin_ID
        arcpy.FeatureVerticesToPoints_management("StreamClip_layer", Stream_EndsPoint, "END")
    #Select
    arcpy.SelectLayerByLocation_management("DissecV_pol_layer", 'INTERSECT', Stream_MidPoints, "0.1", "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("DissecV_pol_layer", 'INTERSECT', Stream_EndsPoint, "0.1", "ADD_TO_SELECTION")

    #Calculate
    dis_value=ContourInterval_par
    arcpy.CalculateField_management ("DissecV_pol_layer", "DissecationV", dis_value, "VB", "")
    arcpy.SelectLayerByAttribute_management ("DissecV_pol_layer", "CLEAR_SELECTION", "")

    ####Calculate other classes
    rows_zones=arcpy.da.SearchCursor("Dissecation_zones_layer", "Zone")
    for zone in rows_zones:
        L=1
        dis_value=ContourInterval_par
        ##Create zone layer
        expressionZone = 'Zone=%s'%zone
        arcpy.MakeFeatureLayer_management ("DissecV_pol_layer", "DissecV_pol_select", expressionZone)
        ##Select "DissecV_pol_layer"
        NC_result=arcpy.GetCount_management("DissecV_pol_select")
        NC=int(NC_result.getOutput(0))
        #print ("NC = %d"%NC)
        while L<=NC:
            L+=1
            dis_value+=ContourInterval_par
            #Build for calculating layer
            arcpy.MakeFeatureLayer_management ("DissecV_pol_select", "ForCalculating_layer", 'DissecationV=0')
            #Build calculated layer
            arcpy.MakeFeatureLayer_management ("DissecV_pol_select", "Calculated_layer", 'DissecationV>0')
            #Select pols for calc
            arcpy.SelectLayerByLocation_management("ForCalculating_layer", 'INTERSECT', "Calculated_layer", "", "NEW_SELECTION")
            arcpy.CalculateField_management ("ForCalculating_layer", "DissecationV", dis_value, "VB", "")
        NC_for=arcpy.GetCount_management("ForCalculating_layer")
        NC_for=int(NC_for.getOutput(0))
        NC_dissec+=NC_for
    arcpy.AddMessage("Dissecação calculada")

    #Delete memory files
    arcpy.Delete_management(BasinBuffer)
    arcpy.Delete_management(BasinBuffer_05)
    arcpy.Delete_management(Stream_EndsPoint)
    arcpy.Delete_management(StreamClip)
    arcpy.Delete_management(BasinLine)
    arcpy.Delete_management(BasinBuffer_05_line)
    arcpy.Delete_management(StreamEnds_buffer)
    arcpy.Delete_management(BasinLine_erase)
    arcpy.Delete_management(BasinLine_dissolve)
    arcpy.Delete_management(BasinPtElev_tab)
    arcpy.Delete_management(ContourClip)
    arcpy.Delete_management(StreamPoints_Multi)
    arcpy.Delete_management(DissecV_inter)
    arcpy.Delete_management(DissecV_point)
    arcpy.Delete_management(DissecV_Zone)
    arcpy.Delete_management(Stream_EndsPoint)
    arcpy.Delete_management(Stream_SlitAtPoints1)
    arcpy.Delete_management(Stream_SlitAtPoints1)
    arcpy.Delete_management(Stream_MidPoints)

if NC_dissec==0:
    arcpy.AddMessage("A dissecação de TODOS os poligonos foram calculadas")
if NC_dissec>0:
    arcpy.AddMessage("ATENÇÃO. Não foi possivel calcular a dissecação de %d poligonos" %NC_dissec)

#Set extend to basins again
descbasins=arcpy.Describe(Basins)
arcpy.env.extent=descbasins.extent  

#Append all DissecV_pol file and generate a Output#
##List all file geodatabases in workfolder
arcpy.env.workspace=WorkFolder
workspaces = arcpy.ListWorkspaces("*", "FileGDB")
fcs=[]
##Append all DissecV_pol
for workspace in workspaces:
    # List all Dissecation FCS in workspaces
    arcpy.env.workspace = workspace
    featureclasses = arcpy.ListFeatureClasses("DissecationV_B*")
    if len (featureclasses)>0:
        fc=featureclasses[0]
        path="%s\%s" % (workspace,fc)
        fcs.append(path)
if len(fcs)>0:
    spatial_reference = arcpy.Describe(fcs[0]).spatialReference
    arcpy.CreateFeatureclass_management(DissecOut_location, DissecOut_name, "POLYGON", "", "", "", spatial_reference)
    target="%s\%s" % (DissecOut_location,DissecOut_name)
    arcpy.AddField_management(target, "DissecationV", "Long", "", "", "", "", "NULLABLE")
    arcpy.Append_management (fcs, target, "NO_TEST")
