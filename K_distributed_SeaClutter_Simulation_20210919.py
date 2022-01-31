'''
Simulate K-distributed Sea clutter.
Created by Yi ZHOU, Sep. 19, 2021@Provence_Dalian.
1. simulate the Gamma process by a Gaussian Process.
K-distribution is a compound distribution. p(x) = \int_{\eta} p(x|eta)p(eta;v)d\eta
The Raleigh distributed speckle p(x;\eta) is modulated by a gamma distribution p(\eta; v).
Furthermore, the gamma distributed texture is correlated in time (several seconds) or spatial.
Therefore we need to model the gamma process, where each point follows the gamma distribution
and at the same time has the auto-correlation function (ACF) R_\gamma(\tau).
This is solved by the finding a Gaussian Process first.
Through the memoryless non-linear transform (MNLT), finding the connection between
ACF of Gamma Process and Gaussian Process, the R_\gamma(\tau) is approximated by the
R_gaussian(\tau) in a polynomial equation.
R_\gamma(\tau) = \sum_{-\infty}^{\infty} \alpha_n R_gaussian(\tau)^n.
In practice, we first pre-set the gamma distribution with known R_\gamma(\tau).
Then according the 'rules of thumb', will find the cor-respondence between
R_\gamma(\tau) and R_\gaussian(\tau), and the random variable in gamma process \eta
and the random variable x in gaussian process.

2. Simulate the Gaussian Process by ACF and white noise.
Finding the format of R_gaussian(\tau), we can get the power spectral density (psd)
S_g(w).
Since the conversion of a white noise G_w(w) to the colored noise G_g(w)
is equal to passing a LTI system response H(jw): G_g(w) = G_w(w)*H(jw)
Then the S_g(w) = |H(jw)|^2 x 1, so
If H(jw) = \sqrt( S_g(w)), Then the colored Gaussian noise is generated by sampling get N
gaussian white noise. G_w[n]
G_g[n] = F^{-1}(F(G_w[n])*H(jw)).

Reference:
[1] Ward   IEE_97
[2] Ward   Book06_ch5.
[3] Brekke IJOE2010
[4] Tough  JPD_1999
[5] Ward   EL_1981
[6] Correlated-noise-and-the-fft, coding in Python
http://kmdouglass.github.io/posts/correlated-noise-and-the-fft/
'''

from numpy.fft import fft, fftshift, ifft, ifftshift
from numpy.fft import fft2, ifft2

import matplotlib.pyplot as plt
import numpy as np
import scipy.special as ss
import scipy.stats as stats
from PIL import Image
import os
#plt.style.use('dark_background')


#uncorrelated gaussian noise
# numSamples = 200
#
# x       = np.arange(numSamples)
# samples = np.random.randn(numSamples)
#
# plt.plot(x, samples, '.-', markersize = 10)
# plt.xlabel('Sample number')
# plt.grid(True)
# plt.show()


def autocorr(x):
    result = np.correlate(x, x, mode='full')
    index  = int(result.size/2)
    return result[index:]

def generate_GP_via_gaussianACF(gaussian_acf):
    '''
    generate Gaussian process via the Gaussian acf function.
    :return:
    '''
    #1 generate white noise samples
    samples_size = gaussian_acf.shape
    Gwn = np.random.normal(loc=0, scale=1, size=samples_size)
    F_Gw = fft(Gwn)
    # correlated Gaussian noise's psd is known as F_Rc
    F_Gaussian_acf=fft(gaussian_acf)
    Gpn = ifft(F_Gw * np.sqrt(F_Gaussian_acf)) # samples in Gaussian process
    return Gpn

def mnlt(x, v):
    '''
    memoryless non-linear transform based on eq(26) of Bekker_IJOE2010
    Note the scipy.special function gammaincinv already divide the factor 1/\Tau(v)
    :return:
    '''
    nlx = 1 - ss.erfc(x/np.sqrt(2))/2
    y = ss.gammaincinv(v, nlx)
    return y

def hermite_polynomials(x, n):
    '''
    compute the hermite polynomials with respect to x.
    :param x: variable
    :param n: order
    :return: H_n(x) = (-1)^n exp(x^2) d^n/dx^n exp(-x^2), this can be computed by the symbol calculus of py
    import sympy as sym
    x = sym.Symbol('x')
    (-1)^n*sym.exp(x**2)*sym.diff(sym.exp(-x**2), x, n)
    '''
    if n>5:
        print('Order greater than 5 is NOT defined!!! Limit n to 5')
        n = 5
    if n==5:
        Hn = 32*(x**5)-160*(x**3) + 120
    if n==4:
        Hn = 16*(x**4) - 48*(x**2) + 12
    if n==3:
        Hn = 8*(x**3) - 12*x
    if n==2:
        Hn = 4*(x**2) - 2
    if n==1:
        Hn = 2*x
    if n==0:
        Hn = 1
    return Hn

import math
def coeff_acf_polyn(x, gamma_cdf_inv):
    '''
    Compute the coefficients of the polynomials with respect to R_G(\tau),
    based on the relation between the ACFs of two Process (Gaussian and Gamma process).
    alpha_n R_G(\tau)^n + .... + alpha_1 R_G(\tau) + alpha_0 - R_T(\tau)
    :param x: x is the samples from a zero-mean unit-variance Gaussian distribution
    :param n:
    :return:
    '''
    coeffs = []
    for n in range(2, -1, -1): #from 5 to 0
        factor = 1/(np.pi*math.factorial(n)*2**n)
        Hn     = hermite_polynomials(x, n)
        alpha_n= np.sum((np.exp(-x**2)*Hn*gamma_cdf_inv))**2
        alpha_n= factor*alpha_n
        coeffs.append(alpha_n)

    #x  = np.random.normal(loc=0, scale = 1, size=f.size)
    return coeffs

def solve_acf_polyn(gamma_acf, coeff_acf_polyn):
    '''
    solve the polynomials of Gaussian acf R_G(\tau), given the Gamma acf R_T(\tau), time-consuming functions.
    :param gamma_acf:
    :param coeff_acf_polyn:
    :return:
    '''
    coeffs       = coeff_acf_polyn.copy()
    gaussian_acf = np.zeros(gamma_acf.shape, dtype=complex)

    if len(gamma_acf.shape)==1:
        Nr = len(gamma_acf)
        for r in range(Nr):
            coeffs[-1] = coeff_acf_polyn[-1] - gamma_acf[r]
            gaussian_acf[r] = np.roots(coeffs)[0]  # solve the acf polynomials for each element.

    if len(gamma_acf.shape)==2:
        Nr, Ntheta = gamma_acf.shape[:2]
        for r in range(Nr):
            for theta in range(Ntheta):
                coeffs[-1] = coeff_acf_polyn[-1] - gamma_acf[r, theta]
                gaussian_acf[r, theta] = np.roots(coeffs)[0] # solve the acf polynomials for each element.

    return gaussian_acf


def correlated_Gamma_noise_via_known_gaussianACF():
    '''
    Generate correlated Gamma_noise via the known Gaussian Autocorrelation Function.
    :return:
    '''
    #Generate correlated Gaussian Noise
    M  = 2**10  # Size of the 1D grid
    L  = 10      # Physical size of the grid
    dx = L / M  # Sampling period
    fs = 1 / dx # Sampling frequency
    df = 1 / L  # Spacing between frequency components
    x  = np.linspace(-L/2,   L/2,   num = M, endpoint = False)
    f  = np.linspace(-fs/2,  fs/2,   num = M, endpoint = False)

    # To check the Power Spectral Density (psd) of the white noise, need to repeat more times.
    # and compute the average psd. The psd of white noise is constant in Frequency domain.
    # F_Rw = 0
    # for i in range(1000):
    #     Gwn   = np.random.normal(loc=0, scale = 1, size=f.size)
    #     Rwn   = autocorr(Gwn)
    #     F_Rwn = fft(Rwn)/f.size
    #     F_Rw += F_Rwn
    # F_Rw = F_Rw/100
    # plt.stem(f, np.real(ifftshift(F_Rw)),  label = 'F')
    # plt.xlim((0, 40))
    # plt.xlabel('Frequency')
    # plt.grid(True)
    # plt.legend()
    # plt.show()
    # print('')

    F_Gcw = 0
    f  = np.linspace(0,  fs,   num = M,   endpoint = True)
    a = 1
    f[0] = f[1]  # change the first zero elements to the next neighbour
    F_Rc = a * (f ** (-1 * 0.6))

    cn = 0
    wn = 0
    gan = 0
    F_rg = 0
    N = 0
    gammap_samples = []
    for i in range(500): #using loop to compute the average psd.
        Gwn   = np.random.normal(loc=0, scale = 1, size=f.size)
        F_Gw  = fft(Gwn)#/np.sqrt(f.size)
        #correlated Gaussian noise's psd is known as F_Rc
        Gcn   = np.real(ifft(F_Gw*np.sqrt(F_Rc)))
        iGwn  = np.real(ifft(F_Gw))
        Rcn   = autocorr(Gcn)
        Frc   = fft(Rcn)/f.size
        F_Gcw += Frc
        cn    += Gcn
        wn    += Gwn
        gan    = mnlt(Gcn, v=1.99)
        Rgan   = autocorr(gan)   #autocorrelation of gamman noise
        F_rga  = fft(Rgan)/f.size
        if np.isnan(F_rga).all()==False:
            N += 1
            F_rg  += F_rga
            gammap_samples.extend(gan)


    import scipy.stats as stats
    fit_alpha, fit_loc, fit_beta=stats.gamma.fit(gammap_samples)
    print('fitted gamma v, loc and beta', fit_alpha, fit_loc, fit_beta)
    a = 1.99
    mean, var, skew, kurt = stats.gamma.stats(a, moments='mvsk')

    fig, ax = plt.subplots(1, 1)


    x = np.linspace(stats.gamma.ppf(0.01, a=1.99, loc=0, scale=1),
                    stats.gamma.ppf(0.99, a=1.99, loc=0, scale=1), 100)
    ax.plot(x, stats.gamma.pdf(x, a=fit_alpha, loc=fit_loc, scale=fit_beta),
           'r-', lw=5, alpha=0.6, label='gamma pdf')


    ax.hist(gammap_samples, density=True, histtype='stepfilled', alpha=0.2)
    ax.legend(loc='best', frameon=False)
    plt.show()


    F_Gcw = F_Gcw /500
    print('gamma psd accumulated times: ', N)
    F_rg  = F_rg/N
    cn = cn/500
    wn = wn /500
    #gan = gan/500
    # plt.plot(cn, label='colored noise')
    # plt.plot(wn, label='whited noise')
    # plt.plot(gan, label='gamma noise')
    plt.plot(f, np.real(F_rg),  label='gamma psd')
    plt.plot(f, np.real(F_Rc),  label='given psd')
    #plt.plot(f, np.real(F_Gcw), label='observed psd')
    # plt.plot(F_Rc, label='psd_colored_noise', color='b')
    # plt.plot(np.abs(F_Gw), label='abs_Gaussian_in_Freq.', color='w')
    # plt.plot(Gwn, label='white noise')
    # plt.plot(Gcn, label='colored noise')
    plt.legend()
    plt.show()
    plt.print('')

def generate_correlated_Gaussian_via_expdecay():
    '''
    Generate correlated Gaussian via exponentially decayed noise
    :return:
    '''
    M = 300  # Size of the 1D grid
    L = 10  # Physical size of the grid
    dx = L / M  # Sampling period
    fs = 1 / dx  # Sampling frequency
    df = 1 / L  # Spacing between frequency components
    #f = np.linspace(-fs / 2, fs / 2, num=M, endpoint=False)

    # To check the Power Spectral Density (psd) of the white noise, need to repeat more times.
    # and compute the average psd. The psd of white noise is constant in Frequency domain.

    Gwn = np.random.normal(loc=0, scale=1, size=(M,M))
    F_Gw = fft2(Gwn)
    fx = np.linspace(0.1, fs, num=M, endpoint=True)
    fy = np.linspace(0.1, fs, num=M, endpoint=True)
    Fx, Fy = np.meshgrid(fx,fy)
    DFs    = np.sqrt(Fx**2+Fy**2)

    a = 1
    #f[0] = f[1]  # change the first zero elements to the next neighbour
    F_Rc = a * (DFs ** (-1 * 0.6))
    Gpn = ifft2(F_Gw*np.sqrt(F_Rc))
    return Gpn

def correlated_Gamma_noise_via_known_gammaACF():
    #Generate correlated Gamma Noise, with known Gamma auto-correlation function.
    M  = 2**10  # Size of the 1D grid
    L  = 10     # Physical size of the grid
    dx = L / M  # Sampling period
    fs = 1 / dx # Sampling frequency
    ts = np.linspace(0,  L,    num=M,    endpoint= True )
    f  = np.linspace(0,  fs,   num = M,  endpoint = True)

    height= 300
    width = 300
    xs    = np.linspace(L,  height,    num=width,    endpoint= True )
    ys    = np.linspace(L,  height,    num=height,    endpoint= True )
    XS,YS    = np.meshgrid(xs, ys)

    v=5 # shape parameter of Gamma distribution

    #Generate the correlated Gamma distribution in time series (1-dimensional)
    #follow the steps of Brekke_IJOE2010 section IV.
    # Gwn             = np.random.normal(loc=0, scale=1, size=f.size)
    # gamma_acf       = 1 + np.exp(-ts/10)*np.cos(ts/8)/v
    # gamma_cdf_inv   = mnlt(Gwn, v=v)
    # coeffs          = coeff_acf_polyn(Gwn, gamma_cdf_inv)
    # coeffs = np.array(coeffs) / coeffs[-1]
    # gaussian_acf = solve_acf_polyn(gamma_acf, coeffs)
    #
    # F_Gw  = fft(Gwn)  # /np.sqrt(f.size)
    # F_Grc = fft(gaussian_acf)
    # G_Gga = fft(gamma_acf)
    # # # correlated Gaussian noise's psd is known as F_Rc
    # Gcn = np.real(ifft(F_Gw * np.sqrt(F_Grc)))
    # Gan = mnlt(Gcn, v=v) #mnlt function is based on eq(26) of Berkker_IJOE2010
    # plt.stem(Gan)
    # plt.show()
    #
    # fit_alpha, fit_loc, fit_beta = stats.gamma.fit(Gan)
    # fig, ax = plt.subplots(1, 1)
    # x = np.linspace(stats.gamma.ppf(0.01, a=v, loc=0, scale=1),
    #                 stats.gamma.ppf(0.99, a=v, loc=0, scale=1), 100)
    # # ax.plot(x, stats.gamma.pdf(x, a=v, loc=0, scale=1),
    # #        'r-', lw=5, alpha=0.6, label='gamma pdf')
    #
    # ax.hist(Gan, density=True, histtype='stepfilled', alpha=0.2)
    # ax.legend(loc='best', frameon=False)
    # plt.show()

    #Generate the correlated Gamma distribution in random filed(2-dimensional)
    Gwn_field       = np.random.normal(loc=0, scale=1, size=(height, width))
    gamma_field_acf = 1 + np.exp(-(XS+YS)/10)*np.cos(np.pi*YS/8)/v
    gamma_cdf_inv_field = mnlt(Gwn_field, v=v)
    coeffs_field    = coeff_acf_polyn(Gwn_field, gamma_cdf_inv_field)
    coeffs_field    = np.array(coeffs_field) / coeffs_field[-1]
    #coeffs = [0.000017, 0.00013, 0.0067, 0.177, 0.816, 1]
    #coeffs = [0.177, 0.816, 1]
    gaussian_field_acf = solve_acf_polyn(gamma_field_acf, coeffs_field)
    #Generate Gamma Process in the field.
    F_Gw_field = fft2(Gwn_field)          # Frequence domain's white noise in field
    F_Grc_field= fft2(gaussian_field_acf) # Frequence domain's colored Gaussian noise. Gaussian process in field
    G_Gga_field= fft2(gamma_field_acf)
    Gcn_field  = np.real(ifft2(F_Gw_field*np.sqrt(F_Grc_field))) #GP samples
    Gan_field  = mnlt(Gcn_field, v=v) #mapping Gp samples in field to the Gamma samples in  field

    assert(np.sum(Gan_field==np.inf))==0
    assert(np.sum(Gan_field==np.nan))==0
    plt.imshow(Gcn_field)
    plt.title('colored Gaussian noise')

    plt.figure()
    plt.imshow(Gan_field)
    plt.title(r'correlated Gamma noise acf $\left\langle \eta(0,0),\eta(x,y) \right\rangle'
              r'=1+\frac{exp(-(x+y)/10)cos(\pi y/8)}{v=%d}$'%v)
    plt.show()

    # plt.plot(f, np.real(G_Gga),  label='gamma psd')
    # #plt.plot(f, np.real(F_Grc),  label='gaussian psd')
    # plt.legend()
    # plt.show()
    return Gan_field

def test_generate_local_gaussian_via_psf():
    '''
    Test generating local gaussian correlation function via point spread function (PSF)
    :return:
    '''
    height = 300
    width  = 300
    xs = np.linspace(-height/2, height/2, num=width, endpoint=True)
    ys = np.linspace(-height/2, height/2, num=height, endpoint=True)
    XS, YS = np.meshgrid(xs, ys)

    A = 5 # range bandwidth for sinc function
    B = height/2 # bearing sigma  for gaussian function
    gaussian_acf = np.sinc(XS/A)*np.exp(-YS**2/(4*B**2)) #eq(28) of Brekke_IJOE2010
    Gpn = generate_GP_via_gaussianACF(gaussian_acf) # complex type
    # plt.imshow(np.real(Gpn))
    # plt.title('local gaussian distributed speckle')
    # plt.show()
    # print('')
    return Gpn

def generate_field_acf(gamma_shape=5):
    '''
    Generating the field acf, using the fixed coeffs_field in all frames to faster the computing.
    :return:
    '''
    v = gamma_shape  # gamma shape parameter of the texture
    # v = 5

    # L     = 1
    height = 300
    width = 300
    xs = np.linspace(10, height, num=width, endpoint=True)  # avoid the 0,0 start point
    ys = np.linspace(10, height, num=height, endpoint=True)
    XS, YS = np.meshgrid(xs, ys)

    # Generate the correlated Gamma distribution in random filed(2-dimensional)
    Gwn_field = np.random.normal(loc=0, scale=1, size=(height, width))
    gamma_field_acf = 1 + np.exp(-(XS + YS) / 10) * np.cos(np.pi * YS / 8) / v  # eq(69) of Tough_JPD_1999
    gamma_cdf_inv_field = mnlt(Gwn_field, v=v)
    coeffs_field = coeff_acf_polyn(Gwn_field, gamma_cdf_inv_field)
    coeffs_field = np.array(coeffs_field) / coeffs_field[-1]
    gaussian_field_acf = solve_acf_polyn(gamma_field_acf, coeffs_field)

    return gamma_field_acf, gaussian_field_acf

def generate_K_distributed_noise_fast(gamma_field_acf, gaussian_field_acf, gamma_shape=5):
    '''
    K distributed noise in fast computing. Regard the gaussian_field_acf is unchanged for all the white noise.
    w(z) = complex gaussian spekcle w^{*}(z)*sqrt(gamma(z))
    amplitude a(z) = |w(z)| is K-distributed noise based on Brekker_IJOE_2010 sec.IV background simulation
    :param gamma_shape:
    :return:
    '''
    v = gamma_shape #gamma shape parameter of the texture

    height,width = gamma_field_acf.shape[:2]
    Gwn_field = np.random.normal(loc=0, scale=1, size=(height, width))


    #Generate Gamma Process in the field.
    F_Gw_field = fft2(Gwn_field)          # Frequence domain's white noise in field
    F_Grc_field= fft2(gaussian_field_acf) # Frequence domain's colored Gaussian noise. Gaussian process in field
    G_Gga_field= fft2(gamma_field_acf)
    Gcn_field  = np.real(ifft2(F_Gw_field*np.sqrt(F_Grc_field))) #GP samples
    Gan_field  = mnlt(Gcn_field, v=v) #mapping Gp samples in field to the Gamma samples in  field

    assert(np.sum(Gan_field==np.inf))==0
    assert(np.sum(Gan_field==np.nan))==0
    # plt.imshow(Gcn_field)
    # plt.title('colored Gaussian noise')
    #
    # plt.figure()
    # plt.imshow(Gan_field)
    # plt.title(r'correlated Gamma noise acf $\left\langle \eta(0,0),\eta(x,y) \right\rangle'
    #           r'=1+\frac{exp(-(x+y)/10)cos(\pi y/8)}{v=%d}$'%v)
    #plt.show()

    #Gpn_field = test_generate_local_gaussian_via_psf()
    Gpn_field = generate_correlated_Gaussian_via_expdecay()

    CKn_field = Gpn_field*np.sqrt(Gan_field) #step 7 of Bekker_IJOE in Sec.IV.A
    Ckn_field_am = np.abs(CKn_field)

    # plt.figure()
    # plt.imshow(Ckn_field_am)
    # plt.title('correlated K distributed noise in random field')
    #plt.show()
    return Ckn_field_am, Gan_field


def generate_K_distributed_noise(gamma_shape=5):
    '''
    K distributed noise
    w(z) = complex gaussian spekcle w^{*}(z)*sqrt(gamma(z))
    amplitude a(z) = |w(z)| is K-distributed noise based on Brekker_IJOE_2010 sec.IV background simulation
    :param gamma_shape:
    :return:
    '''
    v = gamma_shape #gamma shape parameter of the texture
    #v = 5

    #L     = 1
    height= 300
    width = 300
    xs    = np.linspace(10,  height,    num=width,     endpoint= True ) # avoid the 0,0 start point
    ys    = np.linspace(10,  height,    num=height,    endpoint= True )
    XS,YS    = np.meshgrid(xs, ys)

    #Generate the correlated Gamma distribution in random filed(2-dimensional)
    Gwn_field       = np.random.normal(loc=0, scale=1, size=(height, width))
    gamma_field_acf = 1 + np.exp(-(XS+YS)/10)*np.cos(np.pi*YS/8)/v #eq(69) of Tough_JPD_1999
    gamma_cdf_inv_field = mnlt(Gwn_field, v=v)
    coeffs_field    = coeff_acf_polyn(Gwn_field, gamma_cdf_inv_field)
    coeffs_field    = np.array(coeffs_field) / coeffs_field[-1]
    # print(coeffs_field)
    # return 0 ,0
    #coeffs = [0.000017, 0.00013, 0.0067, 0.177, 0.816, 1]
    #coeffs = [0.177, 0.816, 1]
    gaussian_field_acf = solve_acf_polyn(gamma_field_acf, coeffs_field)
    #Generate Gamma Process in the field.
    F_Gw_field = fft2(Gwn_field)          # Frequence domain's white noise in field
    F_Grc_field= fft2(gaussian_field_acf) # Frequence domain's colored Gaussian noise. Gaussian process in field
    G_Gga_field= fft2(gamma_field_acf)
    Gcn_field  = np.real(ifft2(F_Gw_field*np.sqrt(F_Grc_field))) #GP samples
    Gan_field  = mnlt(Gcn_field, v=v) #mapping Gp samples in field to the Gamma samples in  field

    assert(np.sum(Gan_field==np.inf))==0
    assert(np.sum(Gan_field==np.nan))==0
    # plt.imshow(Gcn_field)
    # plt.title('colored Gaussian noise')
    #
    # plt.figure()
    # plt.imshow(Gan_field)
    # plt.title(r'correlated Gamma noise acf $\left\langle \eta(0,0),\eta(x,y) \right\rangle'
    #           r'=1+\frac{exp(-(x+y)/10)cos(\pi y/8)}{v=%d}$'%v)
    #plt.show()

    #Gpn_field = test_generate_local_gaussian_via_psf()
    Gpn_field = generate_correlated_Gaussian_via_expdecay()

    CKn_field = Gpn_field*np.sqrt(Gan_field) #step 7 of Bekker_IJOE in Sec.IV.A
    Ckn_field_am = np.abs(CKn_field)

    # plt.figure()
    # plt.imshow(Ckn_field_am)
    # plt.title('correlated K distributed noise in random field')
    #plt.show()
    return Ckn_field_am, Gan_field

class KField():
    def __init__(self, img_w=300, img_h=300, gamma_shape=5):
        self.img_w      = img_w
        self.img_h      = img_h
        self.gamma_shape= gamma_shape

        xs = np.linspace(10, img_h, num=img_w, endpoint=True)  # avoid the 0,0 start point
        ys = np.linspace(10, img_h, num=img_w, endpoint=True)
        XS, YS = np.meshgrid(xs, ys)

        # Generate the correlated Gamma distribution in random filed(2-dimensional)
        Gwn_field = np.random.normal(loc=0, scale=1, size=(img_h, img_w))
        self.gamma_field_acf = 1 + np.exp(-(XS + YS) / 10) * np.cos(np.pi * YS / 8) / gamma_shape  # eq(69) of Tough_JPD_1999
        gamma_cdf_inv_field = mnlt(Gwn_field, v=gamma_shape)
        coeffs_field = coeff_acf_polyn(Gwn_field, gamma_cdf_inv_field)
        coeffs_field = np.array(coeffs_field) / coeffs_field[-1]
        self.gaussian_field_acf = solve_acf_polyn(self.gamma_field_acf, coeffs_field)
    def generate_K_distributed_noise_fast(self):
        '''
            K distributed noise in fast computing. Regard the gaussian_field_acf is unchanged for all the white noise.
            w(z) = complex gaussian spekcle w^{*}(z)*sqrt(gamma(z))
            amplitude a(z) = |w(z)| is K-distributed noise based on Brekker_IJOE_2010 sec.IV background simulation
            :param gamma_shape:
            :return:
            '''
        v = self.gamma_shape  # gamma shape parameter of the texture

        height, width = self.gamma_field_acf.shape[:2]
        Gwn_field = np.random.normal(loc=0, scale=1, size=(height, width))

        # Generate Gamma Process in the field.
        F_Gw_field = fft2(Gwn_field)  # Frequence domain's white noise in field
        F_Grc_field = fft2(self.gaussian_field_acf)  # Frequence domain's colored Gaussian noise. Gaussian process in field
        G_Gga_field = fft2(self.gamma_field_acf)
        Gcn_field = np.real(ifft2(F_Gw_field * np.sqrt(F_Grc_field)))  # GP samples
        Gan_field = mnlt(Gcn_field, v=v)  # mapping Gp samples in field to the Gamma samples in  field

        assert (np.sum(Gan_field == np.inf)) == 0
        assert (np.sum(Gan_field == np.nan)) == 0
        Gpn_field = generate_correlated_Gaussian_via_expdecay()
        CKn_field = Gpn_field * np.sqrt(Gan_field)  # step 7 of Bekker_IJOE in Sec.IV.A
        Ckn_field_am = np.abs(CKn_field)
        # plt.figure()
        # plt.imshow(Ckn_field_am)
        # plt.title('correlated K distributed noise in random field')
        # plt.show()
        return Ckn_field_am, Gan_field

import time
if __name__=='__main__':

    # for a in range(10):
    #     mean, var, skew, kurt = stats.gamma.stats(a, moments='mvsk')
    #     print(mean, var, skew, kurt)
    #test_generate_local_gaussian_via_psf()
    #correlated_Gamma_noise_via_known_gammaACF()

    # fig, axs = plt.subplots(1, 2)
    #
    #gamma_field_acf, gaussian_field_acf = generate_field_acf(gamma_shape=5)
    atimes = []
    kfield_clutter = KField()
    for i in range(10):
        tcost = time.perf_counter()
        #Ckn_field_am, Gan_field = generate_K_distributed_noise()
        Ckn_field_am, Gan_field = kfield_clutter.generate_K_distributed_noise_fast()
        tcost = time.perf_counter() - tcost
        print('one frame cost ', tcost, ' seconds')
        plt.imshow(Ckn_field_am)
        plt.pause(0.1)
        plt.draw()
        atimes.append(tcost)
    print('time cost for one frame %.2f s'% (np.mean(atimes)))
    # axs[0].imshow(Gan_field)
    # axs[0].set_title('correlated gamma field')
    # axs[1].imshow(np.abs(Ckn_field_am))
    # axs[1].set_title('correlated gaussian field')
    # plt.figure()
    # plt.plot(Ckn_field_am[:,10])
    # plt.plot(Ckn_field_am[:,15])
    # plt.title('target like spiky clutter')
    # plt.show()


    background_dir = '/Users/yizhou/code/taes2021/results/k_distributed_frames'
    # for fid in range(1,51):
    #     Ckn, Gan = generate_K_distributed_noise()
    #     kframe = Image.fromarray(Ckn)
    #     #gframe = Image.fromarray(Gan)
    #     # PIL can save the image in float format as tif.
    #     kframe.save('%s/correlated_k_decay_Gaussian_speckle/%2d.tif'%(background_dir, fid), compress_level=0)
    #     kframe.save('%s/correlated_k_PSF_Guassian_speckle/%2d.tif' % (background_dir, fid), compress_level=0)
    # #     gframe.save('%s/gamma_noise/%2d.tif' % (background_dir, fid), compress_level=0)
    #     print('saved frames ', fid)
        # test = np.array(Image.open('%s/correlated_k_noise/%2d.tif'%(background_dir, fid)))
        # print(test.dtype)

    # Gpn = generate_correlated_Gaussian_via_expdecay()
    # plt.imshow(np.abs(Gpn))
    # plt.show()
    # fig,axs = plt.subplots(1,2)
    # for fid in range(1,52):
    #     #kframe = np.array(Image.open('%s/correlated_k_PSF_Guassian_speckle/%2d.tif' % (background_dir, fid)))
    #     kframe = np.array(Image.open('%s/correlated_k_decay_Gaussian_speckle/%2d.tif' % (background_dir, fid)))
    #     gframe = np.array(Image.open('%s/gamma_noise/%2d.tif' % (background_dir, fid)))
    #     axs[0].imshow(gframe)
    #     axs[1].imshow(kframe)
    #     plt.draw()
    #     plt.pause(0.1)
