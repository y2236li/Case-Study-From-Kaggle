from keras.layers import Dense, Activation
from keras.models import Sequential, load_model
from keras.optimizers import Adam
import numpy as np


class ReplayBuffer(object):
    def __init__(self, max_size, input_shape, n_actions, discrete=False):
        self.mem_size = max_size  #
        self.mem_cntr = 0
        self.discrete = discrete
        self.state_memory = np.zeros((self.mem_size, input_shape))
        self.new_state_memory = np.zeros((self.mem_size, input_shape))
        dtype = np.int8 if self.discrete else np.float32
        self.action_memory = np.zeros((self.mem_size, n_actions), dtype=dtype)
        self.reward_memory = np.zeros((self.mem_size))
        self.terminal_memory = np.zeros(self.mem_size, dtype=np.float32)

    def store_transition(self, state, action, reward, state_, done):
        """
        :param state: old state
        :param action: action in the transition
        :param reward: rewards gain from old state to new state
        :param state_: new state
        :param done: signal for stop moving
        :return: None

        save old state in self.state_memory
        save new state in self.new_state_memory
        save action in self.action_memory
        save reward in self.reward_memory
        save done in terminal memory
        """
        index = self.mem_cntr % self.mem_size
        self.state_memory[index] = state
        self.new_state_memory[index] = state_
        # store one hot encoding of actions to action memory, if appropriate
        if self.discrete:
            actions = np.zeros((self.action_memory.shape[1]))
            actions[action] = 1.0
            self.action_memory[index] = actions
        else:
            self.action_memory[index] = action
        self.reward_memory[index] = reward
        self.terminal_memory[index] = 1 - done
        self.mem_cntr += 1

    def sample_buffer(self, batch_size):
        """
        :param batch_size: size of batch
        :return: old states, actions, rewards, new states, terminal
        sample some transitions from memory
        """
        max_mem = min(self.mem_cntr, self.mem_size)
        batch = np.random.choice(max_mem, batch_size)

        states = self.state_memory[batch]
        actions = self.action_memory[batch]
        rewards = self.reward_memory[batch]
        states_ = self.new_state_memory[batch]
        terminal = self.terminal_memory[batch]

        return states, actions, rewards, states_, terminal


def build_dqn(lr, n_actions, input_dims, fc1_dims, fc2_dims):
    """
    :param lr: Learning rate
    :param n_actions: number of possible actions
    :param input_dims: input dimension
    :param fc1_dims: dimension of first layer fully connected hidden layer
    :param fc2_dims: dimension of second layer fully connected hiden layer
    :return: A neural network model for deep Q learning
    """
    model = Sequential([
        Dense(fc1_dims, input_shape=(input_dims,)),
        Activation('relu'),
        Dense(fc2_dims),
        Activation('relu'),
        Dense(n_actions)
    ])

    model.compile(optimizer=Adam(lr=lr), loss='mse')

    return model


class Agent(object):
    def __init__(self, alpha, gamma, n_actions, epsilon, batch_size,
                 input_dims, epsilon_dec=0.996, epsilon_end=0.01,
                 mem_size=1000000, fname='dqn_model.h5'):
        self.action_space = [i for i in range(n_actions)]
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_dec = epsilon_dec
        self.epsilon_min = epsilon_end
        self.batch_size = batch_size
        self.model_file = fname
        self.memory = ReplayBuffer(mem_size, input_dims, n_actions,
                                   discrete=True)
        self.q_eval = build_dqn(alpha, n_actions, input_dims, 256, 256)

        self.total_steps

    def remember(self, state, action, reward, new_state, done):
        """
        :param state: old state
        :param action: action in the transition
        :param reward: rewards gain from old state to new state
        :param state_: new state
        :param done: signal for stop moving
        :return: None

        Remember decision and store into memories
        """
        self.memory.store_transition(state, action, reward, new_state, done)

    def choose_action(self, state):
        state = state[np.newaxis, :]
        rand = np.random.random()
        if rand < self.epsilon:
            action = np.random.choice(self.action_space)
        else:
            actions = self.q_eval.predict(state)
            action = np.argmax(actions)

        return action

    def learn(self):
        """
        :return: None
        Learn from the last step
        """
        if self.memory.mem_cntr > self.batch_size:
            state, action, reward, new_state, done = \
                self.memory.sample_buffer(self.batch_size)

            action_values = np.array(self.action_space, dtype=np.int8)
            action_indices = np.dot(action, action_values)

            q_eval = self.q_eval.predict(state)  # find the current Q value

            q_next = self.q_eval.predict(new_state)  # find the future Q values at the next state

            q_target = q_eval.copy()

            batch_index = np.arange(self.batch_size, dtype=np.int32)

            q_target[batch_index, action_indices] = reward + self.gamma * np.max(q_next, axis=1) * done
            # change the current Q matrix by reward of the transition plus the max future reward

            _ = self.q_eval.fit(state, q_target, verbose=0)  # fit model

            self.epsilon = self.epsilon * self.epsilon_dec if self.epsilon > \
                                                              self.epsilon_min else self.epsilon_min
            # reduce epsilon

    def save_model(self):
        self.q_eval.save(self.model_file)

    def load_model_(self):
        self.q_eval = load_model(self.model_file)
