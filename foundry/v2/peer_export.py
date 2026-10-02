"""Excel export of the already-displayed peer snapshot. No substrate calls."""
import math
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.chart import LineChart,Reference


def peer_comparison_workbook(snapshot):
    rows=snapshot.get('rows') or []
    if not isinstance(rows,list) or len(rows)>20:raise ValueError('Invalid comparison rows')
    formula_cells=set()
    wb=Workbook();ws=wb.active;ws.title='Comparison'
    selection=snapshot.get('selection') or {}
    ws.append(['Foundry peer comparison'])
    ws.append(['Cohort',str(selection.get('label','Selected cohort'))])
    ws.append(['Captured',str(snapshot.get('generated_at','')),'Model run',str(snapshot.get('run_hash') or 'No modeled run')])
    ws.append(['Snapshot of the displayed comparison. No additional peer observations were retrieved for this export.'])
    ws.append(['Ratio values are percentage points. Missing observations remain blank.'])
    ws.append(['Metric','Filing','Modeled Q12 (%)','Standalone Q12 (%)','Min (%)','P10 (%)','P25 (%)','Median (%)','P75 (%)','P90 (%)','Max (%)','Valid n','Placement','Status / basis'])
    def number(v):
        if v is None:return None
        if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError('Non-finite or nonnumeric comparison value')
        return v
    for r in rows:
        if not isinstance(r,dict):raise ValueError('Invalid metric row')
        b=r.get('band') or {}
        if not isinstance(b,dict):raise ValueError('Invalid percentile band')
        ws.append([str(r.get('label') or r.get('metric')),str(b.get('quarter','')),number(r.get('modeled')),number(r.get('standalone'))]+[number(b.get(k)) for k in ['min','p10','p25','p50','p75','p90','max']]+[number(b.get('n')),str(r.get('placement','')),str(r.get('error') or r.get('note') or ('Extrema unavailable' if b.get('min') is None else ''))])
    meta=wb.create_sheet('Selection and definitions')
    meta.append(['Selection and source definitions'])
    meta.append(['Mode',str(selection.get('mode',''))]);meta.append(['Certificates',', '.join(map(str,selection.get('certs') or []))]);meta.append(['Lending peers only',bool(selection.get('lending'))])
    meta.append(['Captured',str(snapshot.get('generated_at',''))]);meta.append(['Model run',str(snapshot.get('run_hash') or '')]);meta.append(['Method','Displayed browser snapshot; source values are not independently refreshed during export.'])
    meta.append(['Membership','Broad-cohort distributions reflect substrate group membership at each filing quarter; this summary does not enumerate member histories.'])
    meta.append(['Extrema','True observation min/max when supplied. P10/P90 are never substituted.'])
    meta.append(['Alignment','Calendar comparison uses modeled Q12 filing convention. Vintage uses relative opening quarter.'])
    meta.append(['NIM','Modeled total-assets denominator may differ from peer earning-assets denominator. Interpret directionally.'])
    meta.append(['Thin samples','Percentiles over a few named banks are interpolated member values, not a robust distribution.'])
    for r in rows:meta.append([str(r.get('label') or r.get('metric')),str(r.get('source') or ''),str(r.get('provenance') or {})])
    vintage=snapshot.get('vintage');modeled=snapshot.get('modeled') or {}
    if vintage:
        if not isinstance(vintage,dict):raise ValueError("Invalid vintage snapshot")
        corridor=vintage.get('corridor') or {};obs=vintage.get('observations') or []
        if not isinstance(obs,list) or len(obs)>50000 or len(corridor)>12:raise ValueError('Vintage export exceeds bounded snapshot size')
        v=wb.create_sheet('Vintage comparison',1)
        v.append(['Vintage corridor, Q1–Q12']);v.append(['Definition',str(vintage.get('definition') or {})]);v.append(['Fingerprint',str(vintage.get('fingerprint',''))]);v.append(['Metric','Relative quarter','Modeled (%)','Min (%)','P25 (%)','Median (%)','P75 (%)','P90 (%)','Max (%)','Valid n','Coverage'])
        for metric,data in corridor.items():
            ages=data.get('ages') or []
            if len(ages)>12:raise ValueError('Vintage horizon must stop at Q12')
            start=v.max_row+1
            for i,a in enumerate(ages):
                model=(modeled.get(metric) or [])
                v.append([metric,number(a.get('age_q')),number(model[i]) if i<len(model) else None]+[number(a.get(k)) for k in ['min','p25','p50','p75','p90','max']]+[number(a.get('n')),str(a.get('band_type') or ('Suppressed' if a.get('suppressed') else 'Published'))])
            if ages:
                chart=LineChart();chart.title=metric;chart.y_axis.title='Percentage points';chart.x_axis.title='Relative quarter';chart.width=21;chart.height=7.5;chart.display_blanks='gap'
                # Model and median share the same age axis; gaps remain gaps.
                for col in [3,6]:chart.add_data(Reference(v,min_col=col,min_row=start,max_row=v.max_row),titles_from_data=False)
                chart.set_categories(Reference(v,min_col=2,min_row=start,max_row=v.max_row));
                for i,series in enumerate(chart.series):
                    from openpyxl.chart.series import SeriesLabel
                    series.tx=SeriesLabel(v='Modeled' if i==0 else 'Peer median')
                    series.graphicalProperties.line.solidFill='A27831' if i==0 else '343434'
                v.add_chart(chart,'M'+str(start))
        if obs:
            o=wb.create_sheet('Observations');o.append(['Certificate','Bank','Reporting year','Reporting quarter','Relative quarter','Metric','Value (%)'])
            for r in obs:o.append([number(r.get('cert')),str(r.get('name','')),number(r.get('year')),number(r.get('quarter')),number(r.get('age_q')),str(r.get('metric','')),number(r.get('value'))])
            # Curated, small groups get auditable, familiar bank-column calculations.
            certs=sorted({r.get('cert') for r in obs});metrics=list(corridor)
            if len(certs)<=25:
                c=wb.create_sheet('Curated calculations',2);index={(r['cert'],r['metric'],r['age_q']):r['value'] for r in obs};names={r['cert']:r.get('name') or str(r['cert']) for r in obs}
                from openpyxl.utils import get_column_letter
                for metric in metrics:
                    c.append([metric]);header=c.max_row+1;c.append(['Relative quarter']+[names[x] for x in certs]+['Min','Median','Max','Valid n'])
                    for age in range(1,13):
                        row=c.max_row+1;end=get_column_letter(len(certs)+1);rng=f'B{row}:{end}{row}'
                        c.append([age]+[index.get((cert,metric,age)) for cert in certs]+[f'=IF(COUNT({rng})=0,"",MIN({rng}))',f'=IF(COUNT({rng})=0,"",MEDIAN({rng}))',f'=IF(COUNT({rng})=0,"",MAX({rng}))',f'=COUNT({rng})'])
                        for col in range(len(certs)+2,len(certs)+6):formula_cells.add((c.title,c.cell(row,col).coordinate))
                    c.append([])
    for sheet in wb:
        sheet.sheet_view.showGridLines=False;sheet.freeze_panes='C7' if sheet.title=='Comparison' else 'B2'
        for col in range(1,sheet.max_column+1):
            from openpyxl.utils import get_column_letter
            sheet.column_dimensions[get_column_letter(col)].width=30 if col==1 else 17
        for row in sheet:
            for cell in row:
                cell.font=Font(name='Calibri',size=11,color='343434');cell.alignment=Alignment(vertical='center',wrap_text=True)
                if isinstance(cell.value,str) and cell.value.startswith(('=','+','-','@')) and (sheet.title,cell.coordinate) not in formula_cells:cell.data_type='s'
                if isinstance(cell.value,(int,float)):
                    integer=(sheet.title=='Comparison' and cell.column==12) or (sheet.title=='Vintage comparison' and cell.column in (2,10)) or (sheet.title=='Observations' and cell.column in (1,3,4,5))
                    cell.number_format='0' if integer else '0.00'
            sheet.row_dimensions[row[0].row].height=26
        for cell in sheet[1]:cell.font=Font(name='Calibri',size=17,bold=True,color='343434')
        header=6 if sheet.title=='Comparison' else 4 if sheet.title=='Vintage comparison' else 1
        if sheet.title not in ['Selection and definitions','Curated calculations']:
            for cell in sheet[header]:cell.fill=PatternFill('solid',fgColor='343434');cell.font=Font(name='Calibri',size=10,bold=True,color='FFFFFF')
            sheet.auto_filter.ref=f'A{header}:{sheet.cell(sheet.max_row,sheet.max_column).coordinate}'
        if sheet.title=='Comparison':
            for row in sheet.iter_rows(min_row=7,min_col=3,max_col=3):row[0].font=Font(name='Calibri',size=11,bold=True,color='A27831')
        if sheet.title=='Selection and definitions':sheet.column_dimensions['B'].width=95
    return wb
