import numpy as np
import pandas as pd
from pygecko.gc_tools.sequence import MS_Sequence, FID_Sequence
from pygecko.gc_tools.analyte import Analyte
from pygecko.reaction import Reaction_Array, Product_Array
from numpy.lib.recfunctions import unstructured_to_structured


class Analysis:

    '''
    A class wrapping functions to analyze GC data.
    '''

    @staticmethod
    def calc_plate_yield(ms_sequence: MS_Sequence, fid_sequence: FID_Sequence, layout: Reaction_Array|Product_Array,
                         path: str|None = None):

        '''
        Matches GC-MS and GC-FID peaks and quantifies the yields of the reactions.

        Args:
            ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
            fid_sequence (FID_Sequence): FID_Sequence object containing the GC-FID data.
            layout (Reaction_Array|Product_Array): Reaction_Array or Product_Array object containing the reaction
            layout.
            path (str|None, optional): Path to write the results to. Defaults to None.

        Returns:
            np.ndarray: Numpy array containing the quantification results, retention times and smiles for the analytes.
        '''

        return Analysis.__match_and_quantify_plate(ms_sequence, fid_sequence, layout, path, mode='yield')

    @staticmethod
    def calc_plate_conv(ms_sequence: MS_Sequence, fid_sequence: FID_Sequence, layout: Reaction_Array,
                        path: str|None = None, index:int=0):

        '''
        Matches GC-MS and GC-FID peaks and quantifies the conversion of the reactions.

        Args:
            ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
            fid_sequence (FID_Sequence): FID_Sequence object containing the GC-FID data.
            layout (Reaction_Array): Well_Plate object containing the combinatorial reaction layout.
            path (str|None, optional): Path to write the results to. Defaults to None.

        Returns:
            np.ndarray: Numpy array containing the quantification results, retention times and smiles for the analytes.
        '''

        return Analysis.__match_and_quantify_plate(ms_sequence, fid_sequence, layout, path, mode='conv', index=index)

    @staticmethod
    def __match_and_quantify_plate(ms_sequence: MS_Sequence, fid_sequence: FID_Sequence, layout: Reaction_Array,
                                   path: str|None = None, mode:str='yield', index:int=0) -> np.ndarray:

        '''
        Matches GC-MS and GC-FID peaks and quantifies the yields/conversion of the reactions.

        Args:
            ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
            fid_sequence (FID_Sequence): FID_Sequence object containing the GC-FID data.
            layout (Reaction_Array): Well_Plate object containing the combinatorial reaction layout.
            path (str|None, optional): Path to write the results to. Defaults to None.
            mode (str, optional): Parameter (yield or conversion) to quantify. Defaults to 'yield'.

        Returns:
            np.ndarray: Numpy array containing the quantification results, retention times and smiles for the analytes.
        '''

        results_df = pd.DataFrame(columns=['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
                                      index=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])

        results_dict = Analysis.__match_and_quantify(ms_sequence, fid_sequence, layout, mode, index)

        for key, value in results_dict.items():
            results_df.loc[key[0], key[1:]] = value

        results_array = results_df.to_numpy()
        results_array = np.array([row.tolist() for row in results_array])
        dtype = np.dtype([('quantity', float), ('rt_ms', float), ('rt_fid', float)])
        results_array = unstructured_to_structured(results_array[:,:,:-1], dtype=dtype)
        if path:
            if mode == 'yield':
                quantity = 'Yield [%]'
                report_df = pd.DataFrame.from_dict(results_dict, orient='index',
                                                   columns=[quantity, 'RT-MS [min]', 'RT-FID [min]', 'Analyte'])
            else:
                quantity = 'Conversion [%]'
                report_df = pd.DataFrame.from_dict(results_dict, orient='index',
                                                   columns=[quantity, 'RT-MS [min]', 'RT-FID [min]', 'Analyte'])
            report_df.sort_index(inplace=True)
            report_df.to_csv(path)
        return results_array

    @staticmethod
    def __match_and_quantify(ms_sequence: MS_Sequence, fid_sequence: FID_Sequence, layout: Reaction_Array, mode: str,
                             index: int = 0, ) -> dict[str, list[float, str]]:

        '''
                Matches GC-MS and GC-FID peaks and quantifies the yields of the reactions.

                Args:
                    ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
                    fid_sequence (FID_Sequence): FID_Sequence object containing the GC-FID data.
                    layout (Reaction_Array): Well_Plate object containing the combinatorial reaction layout.

                Returns:
                    dict: Dictionary containing the yields, retention times and the analyte smiles for each well.
        '''

        results_dict = {}
        for name, ms_injection in ms_sequence.injections.items():
            fid_injection = fid_sequence[name]
            pos = ms_injection.get_plate_position()
            if mode == 'yield':
                analyte = layout.get_product(ms_injection.get_plate_position())
                pass
            if mode == 'conv':
                analyte = layout.get_substrate(pos, index=index)
            mz_match = ms_injection.match_mol(analyte)

            if mz_match:
                ri_match = fid_injection.match_ri(mz_match.ri, analyte=mz_match.analyte)
                if ri_match:
                    yield_ = fid_injection.quantify(ri_match.rt)
                    if mode == 'conv':
                        yield_ = 100 - yield_
                    results_dict[pos] = [yield_, mz_match.rt, ri_match.rt, analyte]
                else:
                    results_dict[pos] = [np.nan, np.nan, np.nan, '']
            else:
                results_dict[pos] = [np.nan, np.nan, np.nan, '']
        return results_dict


    @staticmethod
    def quantify_analyte(fid_sequence:FID_Sequence, rt:float, analyte:Analyte|None=None) -> dict[str, float]:

        '''
        Returns the yields of Analytes at a given retention time in a FID sequence.

        Args:
            fid_sequence (FID_Sequence): FID_Sequence object containing the GC-FID data.
            rt (float): Retention time to quantify the Analytes at.
            analyte (Analyte): Analyte to quantify.

        Returns:
            dict: Dictionary containing the yields of the Analytes in the FID sequence.
        '''

        yield_dict = {}
        for injection in fid_sequence.injections.values():
            peak = injection.flag_peak(rt, analyte=analyte)
            if peak:
                yield_ = injection.quantify(peak.rt)
            else:
                yield_ = 0
            if injection.plate_pos:
                yield_dict[injection.plate_pos] = yield_
            else:
                yield_dict[injection.sample_name] = yield_
        return yield_dict

    @staticmethod
    def calc_plate_ms_only_yield(ms_sequence: MS_Sequence, layout: Reaction_Array|Product_Array,
                         path: str|None = None):

        '''
        Uses only the GC-MS peaks for a rough quantification of the reactions. For reaction discovery or reducing GC-FID measurements.

        Args:
            ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
            layout (Reaction_Array|Product_Array): Reaction_Array or Product_Array object containing the reaction
            layout.
            path (str|None, optional): Path to write the results to. Defaults to None.

        Returns:
            np.ndarray: Numpy array containing the quantification results, retention times and smiles for the analytes.
        '''

        return Analysis.__ms_only_quantify_plate(ms_sequence, layout, path, mode='yield', ms_quantification_mode='area', relative_to='standard')


    @staticmethod
    def __ms_only_quantify_plate(ms_sequence: MS_Sequence, layout: Reaction_Array,
                                   path: str|None = None, mode:str='yield', index:int=0, ms_quantification_mode:str='area', relative_to:str='standard') -> np.ndarray:

        '''
        Uses only the GC-MS peaks for a rough quantification of the reactions, either conversion or yield.

        Args:
            ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
            layout (Reaction_Array): Well_Plate object containing the combinatorial reaction layout.
            path (str|None, optional): Path to write the results to. Defaults to None.
            mode (str, optional): Parameter (yield or conversion) to quantify. Defaults to 'yield'.
            ms_quantification_mode (str, optional): Methode of MS quantification ('height' or 'area'). Default is 'area'.
            relative_to (str, optional): Reference for the MS quantification ('standard' or 'all'). 'all' refers to all other peaks in the spectra. Default is 'standard'.

        Returns:
            np.ndarray: Numpy array containing the quantification results, retention times and smiles for the analytes.
        '''
        # Dynamic Well plate formatting
        rows = [chr(i) for i in range(65, 65 + layout.array.shape[0])]
        columns = [str(i) for i in range(1, layout.array.shape[1] + 1)]
        results_df = pd.DataFrame(columns=columns, index=rows)


        results_dict = Analysis.__ms_quantify(ms_sequence, layout, mode, ms_quantification_mode, relative_to, index ) 

        for key, value in results_dict.items():
            results_df.loc[key[0], key[1:]] = value

        results_array = results_df.to_numpy()
        results_array = np.array([row.tolist() for row in results_array])
        dtype = np.dtype([('quantity', 'U20'), ('rt_ms', float), ('rt_fid', float)])
        results_array = unstructured_to_structured(results_array[:,:,:-1], dtype=dtype)
        if path:
            if mode == 'yield':
                quantity = 'MS Yield Estimate'
                report_df = pd.DataFrame.from_dict(results_dict, orient='index',
                                                   columns=[quantity, 'RT-MS [min]', 'RT-FID [min]', 'Analyte'])
            else:
                quantity = 'MS Conversion Estimate'
                report_df = pd.DataFrame.from_dict(results_dict, orient='index',
                                                   columns=[quantity, 'RT-MS [min]', 'RT-FID [min]', 'Analyte'])
            report_df.sort_index(inplace=True)
            report_df.to_csv(path)
        return results_array


    @staticmethod
    def __ms_quantify(ms_sequence: MS_Sequence, layout: Reaction_Array, mode: str, ms_quantification_mode: str, relative_to: str,
                             index: int = 0) -> dict[str, list[float, str]]:

        '''
                Searches for the product mass in all peaks of the MS spectra.
                Compares all MS peaks within one injection and roughly estimates the yield either by MS peak height or area.
                The yield estimation can be done relative to the standard or all other peaks in the spectra.

                Args:
                    ms_sequence (MS_Sequence): MS_Sequence object containing the GC-MS data.
                    layout (Reaction_Array): Well_Plate object containing the combinatorial reaction layout.
                    mode (str): Parameter (yield or conversion) to quantify.
                    ms_quantification_mode (str): Methode of MS quantification ('height' or 'area').
                    relative_to (str): Reference for the MS quantification ('standard' or 'all').

                Returns:
                    dict: Dictionary containing the yields, retention times and the analyte smiles for each well.
        '''

        results_dict = {}
        for name, ms_injection in ms_sequence.injections.items():
            pos = ms_injection.get_plate_position()
            if mode == 'yield':
                analyte = layout.get_product(ms_injection.get_plate_position())
                pass
            elif mode == 'conv':
                analyte = layout.get_substrate(pos, index=index)
            else:
                raise ValueError('Mode must be either yield or conv')
            mz_match = ms_injection.match_mol(analyte)

            if mz_match:

                if relative_to == 'all':
                # Calculate the total area or height of all peaks in the injection.
                # Quantification is done relative to all other peaks in the spectra.
                    total_area_or_height = sum(getattr(peak, ms_quantification_mode) for peak in ms_injection.peaks.values())
                    product_area_or_height = getattr(mz_match, ms_quantification_mode)
                    product_ratio = (product_area_or_height / total_area_or_height) * 100

                elif relative_to == 'standard':
                    standard_area_or_height = None
                    for peak in ms_injection.peaks.values():
                        if hasattr(peak, 'flag') and peak.flag == 'standard':
                            standard_area_or_height = getattr(peak, ms_quantification_mode)
                            break
                    if standard_area_or_height is not None:
                        product_area_or_height = getattr(mz_match, ms_quantification_mode)
                        product_ratio = (product_area_or_height / standard_area_or_height) * 100
                    else:
                        print (f'No standard found for {ms_injection.sample_name}.')


                # Classification of the product ratio into qualitative categories for quantification
                if product_ratio >= 70:
                    yield_ = 'excellent'
                elif product_ratio >= 50:
                    yield_ = 'good'
                elif product_ratio >= 20:
                    yield_ = 'fair'
                elif product_ratio >= 5:
                    yield_ = 'poor'
                elif product_ratio < 5:
                    yield_ = 'trace'

                if mode == 'conv':
                    yield_ = 100 - yield_
                results_dict[pos] = [yield_, mz_match.rt, np.nan, analyte]
                print(f'{ms_injection.sample_name:<20} : {product_ratio:<20} : {mz_match.rt:<20} : {mz_match.analyte.mz:<20}\n')
            else:
                results_dict[pos] = [np.nan, np.nan, np.nan, '']
        return results_dict
