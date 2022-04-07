# -*- coding: utf-8 -*-
"""
Created on Tue Feb  8 10:11:52 2022

@author: ggorski

These functions were developed borrowing code and ideas from:
    Laurel Larsen (laurel@berkeley.edu) for Larsen, L. G. and J. W. Harvey. 2017. Disrupted carbon cycling in restored and unrestored urban streams: Critical timescales and controls. Limnology and Oceanography, 62(Suppl. S1), S160-S182, doi: 10.1002/lno.10613. Please cite this work accordingly in products that use this code.
    Edom Modges (edom.moges@berkeley.edu)
    Julianne Quinn University of Virginia
    The transfer entropy routine is based on Ruddell and Kumar, 2009, "Ecohydrologic process networks: 1. Identification," Water Resources Research, 45, doi:10.1029/2008WR007279.

"""

from joblib import Parallel, delayed
import math
import numpy as np
from scipy.stats.stats import pearsonr

#%%
class pre_proc_func:
    '''this class of functions preprocesses the data to remove unwanted signals
    and prepare the data for information theory calculations'''
    def __init__(self):
        pass

    def log10(self, sr):
        l10 = np.log10(sr+1e-6)
        return l10
    
    def standardize(self, sr):
        standardized = (sr - np.nanmean(sr))/np.nanstd(sr, ddof = 1)
        return standardized

    def normalize(self, sr):
        normalized = (sr-np.nanmin(sr))/(np.nanmax(sr)-np.nanmin(sr))
        return normalized
    
    def anomaly(self, sr):
        anomaly = sr - np.nanmean(sr)
        return anomaly

    def remove_seasonal_signal(self, sr):
        #calculate doy for sr
        sr_doy = sr.index.strftime('%j')
        #convert sr_historical to df
        sr_historical_df = sr.to_frame().copy()
        #calculate doy
        sr_historical_df['doy'] = list(sr.index.strftime('%j'))
        #calculate the doy means
        doy_means = sr_historical_df.groupby('doy').mean()
        #convert the index (doy) to int64
        doy_means.index = doy_means.index.astype('int64')
        
        seasonal_removed = list()
        for i in range(len(sr)):
            doy = int(sr_doy[i])
            doy_mean = doy_means.loc[doy]
            value = sr.iloc[i]-doy_mean[0]
            seasonal_removed.append(value)
        return seasonal_removed
    
    

def calc2Dpdf(M,nbins = 11):
    '''calculates the 3 pdfs, one for x, one for y and a joint pdf for x and y 
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source (x) and
    the second column is the sink (y).
    nbins: is the number of bins used for estimating the pdf with a default of 11'''
    
    counts, binEdges = np.histogramdd(M,bins=nbins)
    p_xy = counts/np.sum(counts)
    
    p_x = np.sum(p_xy,axis=1)
    p_y = np.sum(p_xy,axis=0)
    
    return p_x, p_y, p_xy

def calc3Dpdfs(M, nbins = 11):
    '''calculates the 7 pdfs, one each for x, y, and z, one each for their individual
    joint distributions, and one for the 3d joint distributions. Right now it only returns
    the 3d joint distribution for simplicity
    M: a numpy array of shape (nobs, 3) where nobs is the number of observations.
    nbins: is the number of bins used for estimating the pdf with a default of 11'''
    # use numpy histogram as pdf
    pdf,edges = np.histogramdd(M,bins=nbins)
    p_xyz = pdf/np.sum(pdf)
    
    #p_xy = np.sum(p_xyz,axis=2)
    #p_xz = np.sum(p_xyz,axis=1)
    #p_yz = np.sum(p_xyz,axis=0)
    
    #p_x = np.sum(p_xy,axis=1)
    #p_y = np.sum(p_xy,axis=0)
    #p_z = np.sum(p_xz,axis=0)
    
    return p_xyz

def calcEntropy(pdf):
    '''calculate the entropy from the pdf
    here n_0 is used to indicate that all values are non-zero'''
    
    pdf_n_0 = pdf[pdf>0]
    log2_pdf_n_0 = np.log2(pdf_n_0)
    H = (-sum(pdf_n_0*log2_pdf_n_0))
    return H


def calcMI(M, nbins = 11):
    '''calculate mutual information of two variables
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the mutual information is normalized by the entropy of the sink'''
    
    
    p_x, p_y, p_xy = calc2Dpdf(M, nbins = 11)
    
    Hx = calcEntropy(p_x)
    Hy = calcEntropy(p_y)
    Hxy = calcEntropy(p_xy)
    
    MI = (Hx+Hy-Hxy)/Hy
    
    return MI

def calcMI_shuffled(M, nbins = 11):
    '''shuffles the input dataset to destroy temporal relationships for signficance testing
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the mutual information is normalized by the entropy of the sink
    returns a single MI value for a numpy array the same size and shape as M, 
    but with the order shuffled'''
    
    Mss = np.ones(np.shape(M))*np.nan # Initialize
    
    for n in range(np.shape(M)[1]): # Columns are shuffled separately
        n_nans = np.argwhere(~np.isnan(M[:,n]))
        R = np.random.rand(np.shape(n_nans)[0],1)
        I = np.argsort(R,axis=0)
        Mss[n_nans[:,0],n] = M[n_nans[I[:],0],n].reshape(np.shape(M[n_nans[I[:],0],n])[0],)
    MI_shuff = calcMI(Mss, nbins = 11)
    return MI_shuff
    
def calcMI_crit(M, nbins = 11, alpha = 0.05, numiter = 1000, ncores = 2):
    '''calculate the critical threshold of mutual information
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the mutual information is normalized by the entropy of the sink
    alpha: significance threshold, default = 0.05
    numiter: number of iterations, default = 1000
    ncores: number of cores, default = 2'''
    
    MIss = Parallel(n_jobs=ncores)(delayed(calcMI_shuffled)(M, nbins) for ii in range(numiter))
    MIss = np.sort(MIss)
    #print(MIss)
    MIcrit = MIss[math.ceil((1-alpha)*numiter)] 
    return(MIcrit)

def lag_data(M, shift):
    '''lags data by shift for transfer entropy calculation
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arranged such that the first column is the source and
    the second column is the sink.
    shift: the number of time steps you want to lag the sink by, must be a positive integer
    returns M_lagged of dimensions [length(M)-shift, 3]
    M_lagged[,1] = source_lagged: source[1:n-shift]
    M_lagged[,2] = sink_unlagged: sink[shift:n]
    M_lagged[,3] = sink_lagged: sink[1:n-shift]
    => H(Xt-T, Yt, Yt-T)'''
    
    length_M = M.shape[0]
    cols_M = M.shape[1]
    newlength_M = length_M - shift 
    M_lagged = np.nan*np.ones([newlength_M, cols_M+1]) 
    
    M_lagged[:,0] = M[0:(length_M-shift), 0]
    M_lagged[:,1] = M[shift:(length_M),1]
    M_lagged[:,2] = M[0:(length_M-shift),1]
    return M_lagged

def calcTE(M, shift, nbins = 11):
    '''calculate the transfer entropy from source lagged by shift to sink
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the mutual information is normalized by the entropy of the sink'''
    #lag data
    M_lagged = lag_data(M,shift)
    #remove any rows where there is an nan value
    M_short =  M_lagged[~np.isnan(M_lagged).any(axis=1)]
    
    M1 = M_short[:,(0,2)]  # [source_lagged(1:n-shift), sink_lagged(1:n-shift)]  =>H(Xt-T,Yt-T)
    M2 = M_short[:,(1,2)] # [sink_unlagged(shift:n), sink_lagged(1:n-shift)]    =>H(Yt,Yt-T)
    M3 = M_short[:,2]      # [sink_unlagged(1:n-shift)] =>H(Yt-T) 
    
    #calc joint entropy of H(Xt-T,Yt-T)
    _, _, p_xlyl = calc2Dpdf(M1, nbins)
    T1 = calcEntropy(p_xlyl)
    
    #calc joint entropy of H(Yt-T) and H(Yt,Yt-T)
    _, pyl, p_yulyl = calc2Dpdf(M2, nbins)
    T2 = calcEntropy(p_yulyl)
    
    #calc entropy of H(Yt-T)
    T3 = calcEntropy(pyl)
    
    #calc 3d joint entropy 
    p_xlyulyl = calc3Dpdfs(M_short, nbins)
    T4 = calcEntropy(p_xlyulyl)

    T = (T1+T2-T3-T4)/T3 # Knuth formulation of transfer entropy
    
    return T

def calcTE_shuffled(M, shift, nbins = 11):
    '''shuffles the input dataset to destroy temporal relationships for signficance testing
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arranged such that the first column is the source and
    the second column is the sink.
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the transfer entropy is normalized by the entropy of the sink
    returns a single TE value for a numpy array the same size and shape as M, 
    but with the order shuffled'''
    
    Mss = np.ones(np.shape(M))*np.nan # Initialize
    
    for n in range(np.shape(M)[1]): # Columns are shuffled separately
        n_nans = np.argwhere(~np.isnan(M[:,n]))
        R = np.random.rand(np.shape(n_nans)[0],1)
        I = np.argsort(R,axis=0)
        Mss[n_nans[:,0],n] = M[n_nans[I[:],0],n].reshape(np.shape(M[n_nans[I[:],0],n])[0],)
    TE_shuff = calcTE(Mss, shift, nbins = 11)
    return TE_shuff

def calcTE_crit(M, shift, nbins = 11, alpha = 0.05, numiter = 1000, ncores = 2):
    '''calculate the critical threshold of transfer entropy
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    shift: time lag that should be considered
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the transfer entropy is normalized by the entropy of the sink
    alpha: significance threshold, default = 0.05
    numiter: number of iterations, default = 1000
    ncores: number of cores, default = 2'''
    
    TEss = Parallel(n_jobs=ncores)(delayed(calcTE_shuffled)(M, shift, nbins) for ii in range(numiter))
    TEss = np.sort(TEss)
    #print(MIss)
    TEcrit = TEss[math.ceil((1-alpha)*numiter)] 
    return(TEcrit)

def calc_it_metrics(M, Mswap, n_lags, calc_swap = True, nbins = 11, alpha = 0.01):
    '''wrapper function for calculating mutual information and transfer entropy 
    (for both x -> y and y -> x) across a range of time lags. It also calculates
    a significance threshold for mutual information and transfer entropy using the 
    shuffled surrogate method
    M: a numpy array of shape (nobs, 2) where nobs is the number of observations
    this assumes that the data are arrange such that the first column is the source and
    the second column is the sink.
    Mswap: a numpy array identical to M except the two columns have been swapped
    n_lags: number of time lag that should be considered, will calculate from 0-n_lags
    nbins: is the number of bins used for estimating the pdf with a default of 11
    the transfer entropy is normalized by the entropy of the sink
    alpha: significance threshold, default = 0.05
    '''
    
    MI = []
    MIcrit = []
    corr = []
    TE = []
    TEcrit = []
    TEswap = []
    TEcritswap = []
    for i in range(1,n_lags):
        #lag data
        M_lagged = lag_data(M,shift = i)
        #remove any rows where there is an nan value
        M_short =  M_lagged[~np.isnan(M_lagged).any(axis=1)]
        MItemp = calcMI(M_short[:,(0,1)], nbins = nbins)
        MI.append(MItemp)
        MIcrittemp = calcMI_crit(M_short[:,(0,1)], nbins = nbins, ncores = 8, alpha = 0.01)
        MIcrit.append(MIcrittemp)
        
        corrtemp = pearsonr(M_short[:,0], M_short[:,1])[0]
        corr.append(corrtemp)
        
        TEtemp = calcTE(M, shift = i, nbins = nbins)
        TE.append(TEtemp)
        TEcrittemp = calcTE_crit(M, shift = i, nbins = nbins, ncores = 8, alpha = 0.01)
        TEcrit.append(TEcrittemp)
        
        if calc_swap:
            TEtempswap = calcTE(Mswap, shift = i)
            TEswap.append(TEtempswap)
            TEcrittempswap = calcTE_crit(Mswap, shift = i, nbins = nbins, ncores = 8, alpha = 0.01)
            TEcritswap.append(TEcrittempswap)
        
    it_metrics = {'MI':MI, 'MIcrit':MIcrit,
                  'TE':TE, 'TEcrit':TEcrit,
                  'TEswap':TEswap, 'TEcritswap':TEcritswap,
                  'corr':corr}
    
    return it_metrics