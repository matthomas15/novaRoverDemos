'''
Implementation of the fast slam algorithm 
For a step by step implementation please check the Jupyter Notebook
NOTE: 

We do not own the entire code 
The majority of the code is taken from the Python Robotics Repo
https://github.com/AtsushiSakai/PythonRobotics 
'''

import math

import matplotlib.pyplot as plt
import numpy as np

# Fast SLAM covariance
Q = np.diag([3.0, np.deg2rad(10.0)]) ** 2
R = np.diag([1.0, np.deg2rad(20.0)]) ** 2

#  Simulation parameter
Qsim = np.diag([0.3, np.deg2rad(2.0)]) ** 2
Rsim = np.diag([0.5, np.deg2rad(10.0)]) ** 2
OFFSET_YAWRATE_NOISE = 0.01

DT = 0.1  # time tick [s]
SIM_TIME = 50.0  # simulation time [s]
MAX_RANGE = 20.0  # maximum observation range
M_DIST_TH = 2.0  # Threshold of Mahalanobis distance for data association.
STATE_SIZE = 3  # State size [x,y,yaw]
LM_SIZE = 2  # LM srate size [x,y]
N_PARTICLE = 100  # number of particle
NTH = N_PARTICLE / 1.5  # Number of particle for re-sampling

show_animation = True

'''
A class to represent the samples/particles generated by the motion model 
These particles are a prediction about the rover's posterior 
'''
class Particle:

    def __init__(self, N_LM):
        # * As the number of particles increase their weights decrease
        self.w = 1.0 / N_PARTICLE
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        # landmark x-y positions
        self.lm = np.zeros((N_LM, LM_SIZE))
        # landmark position covariance
        self.lmP = np.zeros((N_LM * LM_SIZE, LM_SIZE))

'''
Function: fast_slam 
    A function which implements the three steps of the fast slam algorithm

Parameters: 
    Particles - The samples generated by the motion model
    u - Vehicle controls (inputs) without any noise 
    z - Observation made by sensors without any noise 
'''

def fast_slam1(particles, u, z):
    
    particles = predict_particles(particles, u)

    # update with observations

    particles = resampling(particles) 

    return particles

'''
Function: Motion model 
    The function which will update the position of the rover 
    peridically based on the control 

Parameters: 
    x: A list consisting the state of the rover (x, y, yaw)
    u: Controls given to the rover
'''
def motion_model(x, u):
    # The state matrix 
    # In the demo only an identity matrix 
    F = np.array([[1.0, 0, 0],
                  [0, 1.0, 0],
                  [0, 0, 1.0]])

    # Input matrix
    B = np.array([[DT * math.cos(x[2, 0]), 0],
                  [DT * math.sin(x[2, 0]), 0],
                  [0.0, DT]])

    # Update the position of the rover based on the controls 
    # * Doesn't adjust for any noise
    x = F @ x + B @ u

    # Convert the angle into the first quadrant 
    x[2, 0] = pi_2_pi(x[2, 0])

    return x


'''
Function: calc_input
    This function mimics the vehicle commands. In this case it is instructed 
    to rotate in a circle

Parameters: 
    time - used as simulation time to mimic real life inputs
'''

def calc_input(time):
    if time <= 3.0:  # cwait at first
        v = 0.0
        yawrate = 0.0
    else:
        v = 1.0  # [m/s]
        yawrate = 0.1  # [rad/s]

    u = np.array([v, yawrate]).reshape(2, 1)

    return u


def observation(xTrue, xd, u, RFID):
    # calc true state
    xTrue = motion_model(xTrue, u)

    # add noise to range observation
    z = np.zeros((3, 0))
    for i in range(len(RFID[:, 0])):

        dx = RFID[i, 0] - xTrue[0, 0]
        dy = RFID[i, 1] - xTrue[1, 0]
        # d is the distance between the landmark and the rover.
        d = math.hypot(dx, dy)
        # difference of the angle between the landmark and the rover, and the pose of the rover
        angle = pi_2_pi(math.atan2(dy, dx) - xTrue[2, 0])
        if d <= MAX_RANGE:
            dn = d + np.random.randn() * Qsim[0, 0] ** 0.5  # add noise
            anglen = angle + np.random.randn() * Qsim[1, 1] ** 0.5  # add noise
            zi = np.array([dn, pi_2_pi(anglen), i]).reshape(3, 1)
            # stack the arrays horizontally
            z = np.hstack((z, zi))

    # add noise to input
    ud1 = u[0, 0] + np.random.randn() * Rsim[0, 0] ** 0.5
    ud2 = u[1, 0] + np.random.randn() * Rsim[1, 1] ** 0.5 + OFFSET_YAWRATE_NOISE
    ud = np.array([ud1, ud2]).reshape(2, 1)

    xd = motion_model(xd, ud)

    return xTrue, z, xd, ud


def motion_model(x, u):
    F = np.array([[1.0, 0, 0],
                  [0, 1.0, 0],
                  [0, 0, 1.0]])

    B = np.array([[DT * math.cos(x[2, 0]), 0],
                  [DT * math.sin(x[2, 0]), 0],
                  [0.0, DT]])

    x = F @ x + B @ u

    x[2, 0] = pi_2_pi(x[2, 0])

    return x



def pi_2_pi(angle):
    '''
    Function: pi_2_pi
        A function to convert angle into the first quadrant 

    Parameters: 
        angle - The angle required to convert 
    '''
    return (angle + math.pi) % (2 * math.pi) - math.pi


def predict_particles(particles, u):
    '''
    Function: predict_particles
        A function to execute the first step of the fast_slam which is generating sample
        based on a prediction model. In this case it used the motion model to generate 
        the samples

    Parameters: 
        particles - The samples generated by the particle filter 
        u - Vehicle controls
    '''

    # For each particle produce a new sample
    for i in range(N_PARTICLE):
        px = np.zeros((STATE_SIZE, 1))
        px[0, 0] = particles[i].x
        px[1, 0] = particles[i].y
        px[2, 0] = particles[i].yaw
        # adding noise to the original control
        ud = u + (np.random.randn(1, 2) @ R ** 0.5).T
        # Run the state of particles and the noisy controls through the motion model  
        px = motion_model(px, ud)
        # Update the new state of the particles 
        particles[i].x = px[0, 0]
        particles[i].y = px[1, 0]
        particles[i].yaw = px[2, 0]

    return particles

'''
Function: resampling
    A function used to draw a new set of particles after considering the affect
    of the observations on the particles. Removes mismatch between generated
    particles and the desired posterior.

Paramters:
    particles - The samples generated by the particle filter
'''
def resampling(particles):
    """
    low variance re-sampling
    """

    # normalise the weights of the particles
    particles = normalize_weight(particles)

    # generate an array storing the weights of all the particles 
    pw = []
    for i in range(N_PARTICLE):
        pw.append(particles[i].w)

    pw = np.array(pw)

    # calculate the effective particle number (note the matrix multiplication 
    # has been replaced with the numpy matmul method as the "@" syntax is not
    # valid in Python 2)
    #Neff = 1.0 / (pw @ pw.T)  # Effective particle number
    Neff = 1.0 / (np.matmul(pw, pw.T))  # Effective particle number

    # run the resampling if the effective number of particles is below the set
    # threshold
    if Neff < NTH:  # resampling
        wcum = np.cumsum(pw)
        base = np.cumsum(pw * 0.0 + 1 / N_PARTICLE) - 1 / N_PARTICLE
        resampleid = base + np.random.rand(base.shape[0]) / N_PARTICLE

        # iterate through all the particles and store the indices of those drawn
        # at random based off its weight
        inds = []
        ind = 0
        for ip in range(N_PARTICLE):
            while (ind < wcum.shape[0] - 1) and (resampleid[ip] > wcum[ind]):
                ind += 1
            inds.append(ind)

        # replace particles in the original set with the new set of freshly
        # drawn particles
        tparticles = particles[:]
        for i in range(len(inds)):
            particles[i].x = tparticles[inds[i]].x
            particles[i].y = tparticles[inds[i]].y
            particles[i].yaw = tparticles[inds[i]].yaw
            particles[i].lm = tparticles[inds[i]].lm[:, :]
            particles[i].lmP = tparticles[inds[i]].lmP[:, :]
            particles[i].w = 1.0 / N_PARTICLE

    return particles

'''
Function: normalize_weight
    A function used to normalise the weights associated with each particle in
    order to ensure that the weight ranges between 0 and 1

Paramters:
    particles - The sample generated by the particle filter
'''
def normalize_weight(particles):
    sumw = sum([p.w for p in particles])

    try:
        for i in range(N_PARTICLE):
            particles[i].w /= sumw
    except ZeroDivisionError:
        for i in range(N_PARTICLE):
            particles[i].w = 1.0 / N_PARTICLE

        return particles

    return particles


def main():
    print(__file__ + " start!!")

    time = 0.0

    # RFID positions [x, y]
    # Random Landmark coordinatess
    RFID = np.array([[10.0, -2.0],
                     [15.0, 10.0],
                     [15.0, 15.0],
                     [10.0, 20.0],
                     [3.0, 15.0],
                     [-5.0, 20.0],
                     [-5.0, 5.0],
                     [-10.0, 15.0]
                     ])
    # Counting the number of landmarks       
    N_LM = RFID.shape[0]

    # State Vector [x y yaw v]'
    xEst = np.zeros((STATE_SIZE, 1))  # SLAM estimation
    xTrue = np.zeros((STATE_SIZE, 1))  # True state
    xDR = np.zeros((STATE_SIZE, 1))  # Dead reckoning

    # history
    hxEst = xEst
    hxTrue = xTrue
    hxDR = xTrue

    # Initalise the particles based on the landmarks
    particles = [Particle(N_LM) for _ in range(N_PARTICLE)]

    # Run the program until time runs out
    while SIM_TIME >= time:
        time += DT

        # Generate commands (random)
        u = calc_input(time)

        # Mimic observing sensory data inputs into the rover 
        xTrue, z, xDR, ud = observation(xTrue, xDR, u, RFID)

        # Generate posterior estimation through the fast slam algo
        particles = fast_slam1(particles, ud, z)

        xEst = calc_final_state(particles)

        x_state = xEst[0: STATE_SIZE]

        # store data history
        hxEst = np.hstack((hxEst, x_state))
        hxDR = np.hstack((hxDR, xDR))
        hxTrue = np.hstack((hxTrue, xTrue))

        if show_animation:  # pragma: no cover
            plt.cla()
            # for stopping simulation with the esc key.
            plt.gcf().canvas.mpl_connect('key_release_event',
                    lambda event: [exit(0) if event.key == 'escape' else None])
            plt.plot(RFID[:, 0], RFID[:, 1], "*k")

            for i in range(N_PARTICLE):
                plt.plot(particles[i].x, particles[i].y, ".r")
                plt.plot(particles[i].lm[:, 0], particles[i].lm[:, 1], "xb")

            plt.plot(hxTrue[0, :], hxTrue[1, :], "-b")
            plt.plot(hxDR[0, :], hxDR[1, :], "-k")
            plt.plot(hxEst[0, :], hxEst[1, :], "-r")
            plt.plot(xEst[0], xEst[1], "xk")
            plt.axis("equal")
            plt.grid(True)
            plt.pause(0.001)
       

if __name__ == '__main__':
    main()
